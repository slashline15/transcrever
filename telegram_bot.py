import asyncio
import os
import tempfile
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from openai import OpenAI
from storage import TranscriptionStorage, Transcription
from notion_sync import NotionSync
import time
from dotenv import load_dotenv

load_dotenv()


TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

class TranscriptionBot:
    def __init__(self):
        self.storage = TranscriptionStorage()
        self.notion = NotionSync() if os.getenv("NOTION_TOKEN") else None
        self.openai = OpenAI(api_key=OPENAI_API_KEY)
        self.app = Application.builder().token(TELEGRAM_TOKEN).build()
        self._setup_handlers()
        
        # Cache temporário pra áudios processados
        self.processing_cache = {}
    
    def _setup_handlers(self):
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("last", self.last_transcription))
        self.app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, self.handle_audio))
        self.app.add_handler(CallbackQueryHandler(self.button_callback))
    
    async def start(self, update: Update, context):
        await update.message.reply_text(
            "🎙️ *Bot de Transcrições*\n\n"
            "Envie um áudio ou voice que eu transcrevo!\n\n"
            "Comandos:\n"
            "/last - Última transcrição\n\n"
            "Dica: Responda 'gpt' no áudio pra aprimorar o texto",
            parse_mode='Markdown'
        )
    
    async def handle_audio(self, update: Update, context):
        """Processa áudio recebido."""
        msg = update.message
        
        # Feedback imediato
        status_msg = await msg.reply_text("🎧 Baixando áudio...")
        
        try:
            # Baixa o arquivo
            file_obj = await (msg.voice or msg.audio).get_file()
            
            # Salva temporariamente
            with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as tmp:
                await file_obj.download_to_drive(tmp.name)
                audio_path = tmp.name
            
            # Atualiza status
            await status_msg.edit_text("🎤 Transcrevendo...")
            start_time = time.time()
            
            # Transcreve com Whisper
            with open(audio_path, 'rb') as audio_file:
                response = self.openai.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="pt"
                )
            
            raw_text = response.text.strip()
            duration = (msg.voice or msg.audio).duration or 0
            
            # Verifica se deve aprimorar
            should_enhance = (
                msg.caption and 'gpt' in msg.caption.lower() or
                len(raw_text) > 500  # Auto-aprimora textos longos
            )
            
            enhanced_text = None
            tokens_used = 0
            gpt_model = None
            
            if should_enhance:
                await status_msg.edit_text("✨ Aprimorando com GPT...")
                
                prompt = (
                    "Reescreva o seguinte texto transcrito, corrigindo erros, "
                    "adicionando pontuação adequada e melhorando a fluência. "
                    "Mantenha todo o conteúdo original:\n\n"
                    f"{raw_text}"
                )
                
                gpt_response = self.openai.chat.completions.create(
                    model="gpt-4-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3
                )
                
                enhanced_text = gpt_response.choices[0].message.content.strip()
                tokens_used = len(prompt)//4 + len(enhanced_text)//4  # Estimativa
                gpt_model = "gpt-4-turbo"
            
            # Calcula custo
            cost, _ = self.storage.calculate_cost(
                duration, "whisper-1", gpt_model, 
                tokens_used//2, tokens_used//2
            )
            
            # Salva no banco
            transcription = Transcription(
                raw_text=raw_text,
                enhanced_text=enhanced_text,
                audio_duration=duration,
                whisper_model="whisper-1",
                gpt_model=gpt_model,
                tokens_used=tokens_used,
                cost_usd=cost
            )
            
            tid = self.storage.save_transcription(transcription)
            
            # Sync com Notion (async)
            if self.notion:
                asyncio.create_task(self._sync_notion_async(tid))
            
            # Prepara resposta
            process_time = time.time() - start_time
            
            # Texto a enviar (prefere aprimorado)
            final_text = enhanced_text or raw_text
            
            # Botões pra alternar versões
            keyboard = []
            if enhanced_text:
                keyboard.append([
                    InlineKeyboardButton("📝 Ver Original", callback_data=f"raw_{tid}"),
                ])
            keyboard.append([
                InlineKeyboardButton("📊 Detalhes", callback_data=f"info_{tid}"),
                InlineKeyboardButton("📤 Notion", callback_data=f"notion_{tid}")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
            
            # Envia transcrição
            await status_msg.delete()
            await msg.reply_text(
                f"{'✨ *Texto Aprimorado:*' if enhanced_text else '📝 *Transcrição:*'}\n\n"
                f"{final_text[:4000]}\n\n"
                f"⏱️ {process_time:.1f}s | 💰 ${cost:.3f}",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
            # Limpa arquivo temporário
            os.unlink(audio_path)
            
        except Exception as e:
            await status_msg.edit_text(f"❌ Erro: {str(e)}")
    
    async def _sync_notion_async(self, tid: int):
        """Sync com Notion em background."""
        try:
            await asyncio.to_thread(self.notion.create_transcription_page, tid)
        except:
            pass  # Fail silently
    
    async def button_callback(self, update: Update, context):
        query = update.callback_query
        await query.answer()
        
        action, tid = query.data.split('_')
        tid = int(tid)
        
        t = self.storage.get_transcription(tid)
        if not t:
            await query.answer("Transcrição não encontrada", show_alert=True)
            return
        
        if action == "raw":
            await query.message.reply_text(
                f"📝 *Original (sem correções):*\n\n{t.raw_text[:4000]}",
                parse_mode='Markdown'
            )
        
        elif action == "info":
            info_text = (
                f"📊 *Detalhes da Transcrição #{t.id}*\n\n"
                f"📅 Data: {t.created_at}\n"
                f"⏱️ Duração: {t.audio_duration}s\n"
                f"🎤 Modelo: {t.whisper_model}\n"
                f"🤖 GPT: {t.gpt_model or 'Não usado'}\n"
                f"🔤 Tokens: {t.tokens_used}\n"
                f"💰 Custo: ${t.cost_usd:.4f}\n"
                f"📏 Caracteres: {len(t.raw_text)} → {len(t.enhanced_text or t.raw_text)}"
            )
            await query.message.reply_text(info_text, parse_mode='Markdown')
        
        elif action == "notion":
            if self.notion:
                await query.answer("📤 Enviando para Notion...")
                try:
                    page_id = await asyncio.to_thread(
                        self.notion.create_transcription_page, tid
                    )
                    if page_id:
                        await query.message.reply_text(
                            "✅ Salvo no Notion com sucesso!"
                        )
                    else:
                        await query.answer("Erro ao salvar no Notion", show_alert=True)
                except Exception as e:
                    await query.answer(f"Erro: {str(e)}", show_alert=True)
            else:
                await query.answer("Notion não configurado", show_alert=True)
    
    async def last_transcription(self, update: Update, context):
        """Mostra última transcrição do banco."""
        transcriptions = self.storage.get_recent_transcriptions(1)
        
        if not transcriptions:
            await update.message.reply_text("Nenhuma transcrição encontrada")
            return
        
        t = transcriptions[0]
        text = t.enhanced_text or t.raw_text
        
        keyboard = [
            [
                InlineKeyboardButton("📝 Original", callback_data=f"raw_{t.id}"),
                InlineKeyboardButton("📊 Info", callback_data=f"info_{t.id}")
            ]
        ]
        
        await update.message.reply_text(
            f"📋 *Última transcrição:*\n\n{text[:4000]}",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    def run(self):
        print("🤖 Bot iniciado! Envie /start no Telegram")
        self.app.run_polling()

if __name__ == "__main__":
    if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
        print("❌ Configure TELEGRAM_BOT_TOKEN e OPENAI_API_KEY no .env")
        exit(1)
    
    bot = TranscriptionBot()
    bot.run()