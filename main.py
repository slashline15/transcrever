# python main.py

"""
Gravador de Áudio v2 - Refatorado com histórico e custos
Sprints 0-2 implementados
"""

import customtkinter as ctk
from datetime import datetime, timedelta
import threading
import queue
import pystray
from plyer import notification
from plyer.platforms.win.notification import instance as _get_notifier
from PIL import Image, ImageDraw
import keyboard
from dotenv import load_dotenv
import time
import os
import sys
from openai import OpenAI

# Importa módulos novos
from audio_core import AudioRecorder
from storage import TranscriptionStorage, Transcription

load_dotenv()

# Configurações
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Configurações padrão
DEFAULT_CONFIG = {
    "shortcuts": {
        "record": "ctrl+shift+r",
        "stop": "ctrl+shift+s",
        "history": "ctrl+shift+h"
    },
    "whisper_model": "whisper-1",
    "gpt_model": "gpt-4-turbo",
    "use_gpt_enhancement": True,
    "auto_start_minimized": True
}

def create_image():
    """Cria ícone para bandeja."""
    width = 64
    height = 64
    image = Image.new("RGB", (width, height), "blue")
    dc = ImageDraw.Draw(image)
    dc.ellipse([10, 10, 54, 54], fill="white")
    dc.ellipse([20, 20, 44, 44], fill="red")
    return image

def estimate_tokens(text: str) -> int:
    """Estima número de tokens (aproximado)."""
    return len(text) // 4

class GravadorWidget:
    def __init__(self):
        # Configuração inicial
        self.config = DEFAULT_CONFIG.copy()
        self.message_queue = queue.Queue()
        
        # Inicializa módulos
        self.audio_recorder = AudioRecorder()
        self.audio_recorder.set_status_callback(self._on_audio_status)
        
        self.storage = TranscriptionStorage()
        
        # Estado
        self.current_transcription_id = None
        self.processing_start_time = None
        
        # Interface
        self._setup_ui()
        self._setup_tray()
        self._register_hotkeys()
        
        # Loops de atualização
        self.update_timer()
        self.check_messages()
        self.update_status_display()
        
        # Minimiza se configurado
        if self.config.get("auto_start_minimized", True):
            self.root.after(100, self.root.withdraw)
        
        # Verifica API
        if not OPENAI_API_KEY:
            self.add_log("⚠️ OPENAI_API_KEY não configurada!", "warning")
            self.show_notification("Aviso", "Configure a chave da API no arquivo .env")
    
    def _setup_ui(self):
        """Configura interface principal."""
        self.root = ctk.CTk()
        self.root.title("Gravador de Áudio v2")
        self.root.geometry("500x700")
        
        # Frame principal
        self.main_frame = ctk.CTkFrame(self.root)
        self.main_frame.pack(pady=20, padx=20, fill="both", expand=True)
        
        # Timer
        self.time_label = ctk.CTkLabel(self.main_frame, text="00:00:00", font=("Arial", 28))
        self.time_label.pack(pady=10)
        
        # Status
        self.status_label = ctk.CTkLabel(self.main_frame, text="Pronto para gravar", wraplength=450)
        self.status_label.pack(pady=5)
        
        # Indicador visual
        self.recording_indicator = ctk.CTkLabel(self.main_frame, text="●", font=("Arial", 24), text_color="gray")
        self.recording_indicator.pack(pady=5)
        
        # Barra de progresso
        self.progress_bar = ctk.CTkProgressBar(self.main_frame, width=400)
        self.progress_bar.pack(pady=10)
        self.progress_bar.set(0)
        
        # Frame de estatísticas
        stats_frame = ctk.CTkFrame(self.main_frame)
        stats_frame.pack(pady=10, fill="x", padx=20)
        
        self.stats_label = ctk.CTkLabel(stats_frame, text="", font=("Arial", 10))
        self.stats_label.pack()
        
        # Botões principais
        button_frame = ctk.CTkFrame(self.main_frame)
        button_frame.pack(pady=10)
        
        self.record_button = ctk.CTkButton(
            button_frame,
            text=f"▶️ Gravar ({self.config['shortcuts']['record'].upper()})",
            command=self.toggle_recording,
            fg_color="red",
            hover_color="darkred",
            width=200
        )
        self.record_button.grid(row=0, column=0, padx=5, pady=5)
        
        self.finish_button = ctk.CTkButton(
            button_frame,
            text=f"⏹️ Finalizar ({self.config['shortcuts']['stop'].upper()})",
            command=self.finish_recording,
            width=200
        )
        self.finish_button.grid(row=0, column=1, padx=5, pady=5)
        
        # Opções
        options_frame = ctk.CTkFrame(self.main_frame)
        options_frame.pack(pady=10)
        
        self.use_gpt_var = ctk.BooleanVar(value=self.config["use_gpt_enhancement"])
        self.gpt_checkbox = ctk.CTkCheckBox(
            options_frame,
            text="Aprimorar texto com GPT-4",
            variable=self.use_gpt_var,
            command=self.toggle_gpt_enhancement
        )
        self.gpt_checkbox.pack(side="left", padx=10)
        
        # Botão de histórico
        self.history_button = ctk.CTkButton(
            options_frame,
            text=f"📋 Histórico ({self.config['shortcuts']['history'].upper()})",
            command=self.show_history,
            width=150
        )
        self.history_button.pack(side="left", padx=10)
        
        # Logs
        self.log_textbox = ctk.CTkTextbox(self.main_frame, width=450, height=200)
        self.log_textbox.configure(state="disabled")
        self.log_textbox.pack(pady=10)
        
        # Custo total
        self.cost_label = ctk.CTkLabel(
            self.main_frame, 
            text="Custo total: $0.00", 
            font=("Arial", 12, "bold")
        )
        self.cost_label.pack(pady=5)
        
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)
        
        # Atualiza estatísticas
        self._update_statistics()
    
    def _setup_tray(self):
        """Configura ícone da bandeja."""
        image = create_image()
        menu = pystray.Menu(
            pystray.MenuItem('Mostrar', self.show_window),
            pystray.MenuItem('Histórico', self.show_history),
            pystray.MenuItem('Sair', self.exit_app)
        )
        self.tray_icon = pystray.Icon("Gravador", image, "Gravador de Áudio v2", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()
    
    def _register_hotkeys(self):
        """Registra atalhos de teclado."""
        try:
            keyboard.add_hotkey(self.config['shortcuts']['record'], self.toggle_recording)
            keyboard.add_hotkey(self.config['shortcuts']['stop'], self.finish_recording)
            keyboard.add_hotkey(self.config['shortcuts']['history'], self.show_history)
            self.add_log(f"✅ Atalhos registrados", "success")
        except Exception as e:
            self.add_log(f"⚠️ Erro nos atalhos: {str(e)}", "warning")
    
    def _on_audio_status(self, status: str):
        """Callback de status do gravador de áudio."""
        self.message_queue.put({
            'type': 'audio_status',
            'status': status
        })
    
    def add_log(self, message: str, level: str = "info"):
        """Adiciona log com timestamp e nível."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Cores por nível
        colors = {
            "info": "",
            "success": "green",
            "warning": "orange", 
            "error": "red"
        }
        
        log_message = f"{timestamp} - {message}\n"
        
        self.log_textbox.configure(state="normal")
        if level in colors and colors[level]:
            self.log_textbox.insert("end", log_message, level)
            self.log_textbox.tag_config(level, foreground=colors[level])
        else:
            self.log_textbox.insert("end", log_message)
        
        self.log_textbox.configure(state="disabled")
        self.log_textbox.see("end")
    
    def update_progress(self, value: float, text: str = ""):
        """Atualiza barra de progresso."""
        self.progress_bar.set(value)
        if text:
            self.status_label.configure(text=text)
    
    def _update_statistics(self):
        """Atualiza estatísticas na UI."""
        stats = self.storage.get_statistics()
        
        stats_text = (
            f"Total: {stats['total_transcriptions']} transcrições | "
            f"{stats['total_duration_minutes']:.1f} min | "
            f"{stats['total_tokens']:,} tokens"
        )
        self.stats_label.configure(text=stats_text)
        self.cost_label.configure(text=f"Custo total: ${stats['total_cost_usd']:.2f}")
    
    def check_messages(self):
        """Processa mensagens da fila."""
        try:
            while True:
                msg = self.message_queue.get_nowait()
                
                if msg['type'] == 'audio_status':
                    # Status do gravador de áudio
                    status_map = {
                        'recording_started': '🔴 Gravação iniciada',
                        'recording_paused': '⏸️ Gravação pausada',
                        'recording_resumed': '▶️ Gravação retomada',
                        'recording_stopped': '⏹️ Gravação finalizada'
                    }
                    texto = status_map.get(msg['status']) or msg['status'] or ""
                    self.add_log(texto)
                    
                elif msg['type'] == 'progress':
                    self.update_progress(msg['value'], msg.get('text', ''))
                    
                elif msg['type'] == 'log':
                    self.add_log(msg['text'], msg.get('level', 'info'))
                    
                elif msg['type'] == 'status':
                    self.status_label.configure(text=msg['text'])
                    
                elif msg['type'] == 'finish':
                    self.update_progress(1.0, "✅ Concluído!")
                    self.root.after(2000, self.reset_ui)
                    self._update_statistics()
                    
        except queue.Empty:
            pass
        
        self.root.after(100, self.check_messages)
    
    def update_timer(self):
        """Atualiza timer de gravação."""
        if self.audio_recorder.is_recording:
            stats = self.audio_recorder.recording_stats
            duration = timedelta(seconds=int(stats['duration']))
            self.time_label.configure(text=str(duration))
            
            # Atualiza indicador
            queue_size = stats['queue_size']
            if queue_size > 50:
                self.add_log(f"⚠️ Fila de áudio alta: {queue_size}", "warning")
        
        self.root.after(100, self.update_timer)
    
    def update_status_display(self):
        """Atualiza indicadores visuais."""
        if self.audio_recorder.is_recording:
            self.recording_indicator.configure(text_color="red")
        else:
            self.recording_indicator.configure(text_color="gray")
        
        self.root.after(100, self.update_status_display)
    
    def toggle_recording(self):
        """Alterna gravação."""
        stats = self.audio_recorder.recording_stats
        
        if stats['status'] == 'idle':
            # Inicia nova gravação
            if self.audio_recorder.start_recording():
                self.record_button.configure(
                    text=f"⏸️ Pausar ({self.config['shortcuts']['record'].upper()})",
                    fg_color="orange"
                )
                self.status_label.configure(text="🎙️ Gravando...")
                self.show_notification("Gravação Iniciada", "Microfone ativo")
                
        elif stats['status'] == 'recording':
            # Pausa
            if self.audio_recorder.pause_recording():
                self.record_button.configure(
                    text=f"▶️ Continuar ({self.config['shortcuts']['record'].upper()})",
                    fg_color="red"
                )
                self.status_label.configure(text="⏸️ Pausado")
                
        elif stats['status'] == 'paused':
            # Retoma
            if self.audio_recorder.resume_recording():
                self.record_button.configure(
                    text=f"⏸️ Pausar ({self.config['shortcuts']['record'].upper()})",
                    fg_color="orange"
                )
                self.status_label.configure(text="🎙️ Gravando...")
    
    def finish_recording(self):
        """Finaliza gravação e processa."""
        audio_file = self.audio_recorder.stop_recording()
        
        if not audio_file:
            self.add_log("⚠️ Nenhum áudio para processar", "warning")
            return
        
        stats = self.audio_recorder.recording_stats
        duration = stats['duration']
        
        self.processing_start_time = time.time()
        self.update_progress(0.1, "📝 Preparando transcrição...")
        
        # Processa em thread separada
        thread = threading.Thread(
            target=self._process_transcription,
            args=(audio_file, duration),
            daemon=True
        )
        thread.start()
    
    def _process_transcription(self, audio_file: str, duration: float):
        """Processa transcrição em thread separada."""
        try:
            # Fase 1: Transcrição
            self.message_queue.put({
                'type': 'progress',
                'value': 0.2,
                'text': '🎤 Enviando para Whisper...'
            })
            
            client = OpenAI(api_key=OPENAI_API_KEY)
            
            with open(audio_file, "rb") as f:
                response = client.audio.transcriptions.create(
                    model=self.config["whisper_model"],
                    file=f,
                    language="pt"
                )
            
            raw_text = response.text.strip()
            
            self.message_queue.put({
                'type': 'log',
                'text': f'✅ Transcrição: {len(raw_text)} caracteres',
                'level': 'success'
            })
            
            # Fase 2: Aprimoramento (opcional)
            enhanced_text = None
            tokens_used = 0
            gpt_model = None
            
            if self.config["use_gpt_enhancement"]:
                self.message_queue.put({
                    'type': 'progress',
                    'value': 0.5,
                    'text': '🤖 Aprimorando com GPT-4...'
                })
                
                prompt = (
                    "Reescreva o seguinte texto transcrito, corrigindo erros, "
                    "adicionando pontuação e melhorando a fluência. "
                    "Mantenha o conteúdo original.\n\n"
                    f"{raw_text}"
                )
                
                # Estima tokens
                input_tokens = estimate_tokens(prompt)
                
                response = client.chat.completions.create(
                    model=self.config["gpt_model"],
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3
                )
                if response.choices[0].message.content:
                    enhanced_text = response.choices[0].message.content.strip()
                else:
                    enhanced_text = raw_text        # Fallback para texto original
                
                output_tokens = estimate_tokens(enhanced_text)
                tokens_used = input_tokens + output_tokens
                gpt_model = self.config["gpt_model"]
                
                self.message_queue.put({
                    'type': 'log',
                    'text': f'✅ Aprimorado: ~{tokens_used} tokens',
                    'level': 'success'
                })
            
            # Fase 3: Salvar
            self.message_queue.put({
                'type': 'progress',
                'value': 0.8,
                'text': '💾 Salvando transcrição...'
            })
            
            # Calcula custo
            cost, _ = self.storage.calculate_cost(
                duration,
                self.config["whisper_model"],
                gpt_model,
                tokens_used // 2,
                tokens_used // 2
            )
            
            # Salva transcrição
            transcription = Transcription(
                raw_text=raw_text,
                enhanced_text=enhanced_text,
                audio_duration=duration,
                whisper_model=self.config["whisper_model"],
                gpt_model=gpt_model,
                tokens_used=tokens_used,
                cost_usd=cost
            )
            
            transcription_id = self.storage.save_transcription(transcription)
            self.current_transcription_id = transcription_id
            
            # Copia para clipboard
            self.storage.copy_to_clipboard(transcription_id)
            
            # Calcula tempo total
            if self.processing_start_time:
                total_time = time.time() - self.processing_start_time
            else:
                total_time = 0
            
            
            self.message_queue.put({
                'type': 'log',
                'text': f'💰 Custo: ${cost:.4f} | ⏱️ Tempo: {total_time:.1f}s',
                'level': 'info'
            })
            
            self.message_queue.put({
                'type': 'progress',
                'value': 1.0,
                'text': '✅ Copiado para área de transferência!'
            })
            
            self.message_queue.put({'type': 'finish'})
            
            self.show_notification(
                "Transcrição Concluída",
                f"Copiado! Custo: ${cost:.3f}"
            )
            
            # Limpa arquivo temporário
            try:
                os.unlink(audio_file)
            except:
                pass
                
        except Exception as e:
            error_msg = str(e)
            if error_msg:
                self.message_queue.put({
                    'type': 'log',
                    'text': f'❌ Erro: {error_msg}',
                    'level': 'error'
                })
            self.message_queue.put({
                'type': 'log',
                'text': f'❌ Erro: {str(e)}',
                'level': 'error'
            })
            self.message_queue.put({
                'type': 'progress',
                'value': 0,
                'text': '❌ Erro no processamento'
            })
    
    def show_history(self):
        """Mostra janela de histórico."""
        history_window = ctk.CTkToplevel(self.root)
        history_window.title("📋 Histórico de Transcrições")
        history_window.geometry("600x400")
        
        # Frame principal
        frame = ctk.CTkFrame(history_window)
        frame.pack(pady=10, padx=10, fill="both", expand=True)
        
        # Lista de transcrições
        history = self.storage.get_clipboard_history(20)
        
        if not history:
            label = ctk.CTkLabel(frame, text="Nenhuma transcrição no histórico")
            label.pack(pady=50)
            return
        
        # Scrollable frame
        scroll_frame = ctk.CTkScrollableFrame(frame, width=550, height=300)
        scroll_frame.pack(pady=10, padx=10, fill="both", expand=True)
        
        for transcription, copied_at in history:
            # Frame para cada item
            item_frame = ctk.CTkFrame(scroll_frame)
            item_frame.pack(pady=5, padx=5, fill="x")
            
            # Texto preview (primeiros 100 chars)
            text = transcription.to_clipboard_text()
            preview = text[:100] + "..." if len(text) > 100 else text
            
            # Info
            info_text = (
                f"{copied_at} | "
                f"{transcription.audio_duration:.1f}s | "
                f"${transcription.cost_usd:.4f}"
            )
            
            info_label = ctk.CTkLabel(
                item_frame,
                text=info_text,
                font=("Arial", 10),
                anchor="w"
            )
            info_label.pack(pady=2, padx=10, anchor="w")
            
            preview_label = ctk.CTkLabel(
                item_frame,
                text=preview,
                wraplength=500,
                anchor="w"
            )
            preview_label.pack(pady=2, padx=10, anchor="w")
            
            # Botão copiar
            copy_btn = ctk.CTkButton(
                item_frame,
                text="📋 Copiar",
                width=80,
                command=lambda tid=transcription.id: self._copy_from_history(tid) if tid else None
            )
            copy_btn.pack(side="right", padx=10)
        
        # Mostra janela
        history_window.transient(self.root)
        history_window.grab_set()
    
    def _copy_from_history(self, transcription_id: int):
        """Copia transcrição do histórico."""
        # CORREÇÃO: Verifica ID válido
        if transcription_id is None:
            return
            
        if self.storage.copy_to_clipboard(transcription_id):
            self.show_notification("Copiado!", "Transcrição copiada do histórico")
            self.add_log("📋 Transcrição copiada do histórico", "success")
    
    def toggle_gpt_enhancement(self):
        """Alterna uso do GPT."""
        self.config["use_gpt_enhancement"] = self.use_gpt_var.get()
        status = "ativado" if self.config["use_gpt_enhancement"] else "desativado"
        self.add_log(f"GPT-4 {status}", "info")
    
    def reset_ui(self):
        """Reseta interface para próxima gravação."""
        self.record_button.configure(
            text=f"▶️ Gravar ({self.config['shortcuts']['record'].upper()})",
            fg_color="red"
        )
        self.progress_bar.set(0)
        self.status_label.configure(text="Pronto para gravar")
        self.time_label.configure(text="00:00:00")
    
    def show_notification(self, title: str, message: str):
        """Mostra notificação do sistema no Windows via plyer."""
        try:
            notifier = _get_notifier()       # isto é um WindowsNotification()
            notifier.notify(                 # ou notifier._notify(...) se preferir
                title=title,
                message=message,
                app_name="Gravador de Áudio v2",
                timeout=3
            )
        except Exception:
            pass

    
    def show_window(self, icon=None, item=None):
        """Mostra janela principal."""
        self.root.after(0, self.root.deiconify)
    
    def hide_window(self):
        """Esconde janela."""
        self.root.withdraw()
    
    def exit_app(self, icon=None, item=None):
        """Fecha aplicação."""
        self.audio_recorder._cleanup()
        self.root.after(0, self.root.quit)
        self.tray_icon.stop()

if __name__ == "__main__":
    if not OPENAI_API_KEY:
        print("ERRO: Configure OPENAI_API_KEY no arquivo .env")
        sys.exit(1)
        
    try:
        app = GravadorWidget()
        app.root.mainloop()
    except KeyboardInterrupt:
        print("\nEncerrando...")
        sys.exit(0)
    except Exception as e:
        print(f"Erro fatal: {e}")
        sys.exit(1)