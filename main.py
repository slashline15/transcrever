import sounddevice as sd
import soundfile as sf
import numpy as np
from openai import OpenAI
import pyperclip
import keyboard
from dotenv import load_dotenv
import time
import os
import customtkinter as ctk
from datetime import datetime, timedelta
import threading
import queue

load_dotenv()

# Configurações
FS = 16000                                        # Frequência de amostragem
ARQUIVO_AUDIO = "gravacao.wav"                    # Nome do arquivo de áudio
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")      # Chave da OpenAI

# Variáveis globais
audio_segments = []     # Armazena os pedaços de áudio gravados
stream = None           # Referência para o stream de áudio
is_recording = False    # Flag para indicar se está gravando
finish = False          # Flag para finalizar a gravação
start_time = None       # Tempo de início da gravação
message_queue = queue.Queue()  # Fila para comunicação entre threads

class GravadorWidget:
    def __init__(self):
        # 1. Configuração inicial da janela
        self.root = ctk.CTk()
        self.root.title("Gravador de Áudio")
        self.root.geometry("400x450")  # Ajustei a altura para acomodar a área de logs
        
        # 2. Criação do frame principal
        self.frame = ctk.CTkFrame(self.root)
        self.frame.pack(pady=20, padx=20, fill="both", expand=True)
        
        # 3. Elementos visuais
        self.time_label = ctk.CTkLabel(self.frame, text="00:00:00", font=("Arial", 24))
        self.time_label.pack(pady=10)
        
        self.status_label = ctk.CTkLabel(self.frame, text="Pronto para gravar", wraplength=350)
        self.status_label.pack(pady=5)
        
        self.recording_indicator = ctk.CTkLabel(self.frame, text="●", font=("Arial", 24), text_color="gray")
        self.recording_indicator.pack(pady=5)
        
        self.segments_label = ctk.CTkLabel(self.frame, text="Segmentos gravados: 0", font=("Arial", 12))
        self.segments_label.pack(pady=5)
        
        self.record_button = ctk.CTkButton(
            self.frame,
            text="▶️ Gravar (F9)",
            command=self.toggle_recording,
            fg_color="red",
            hover_color="darkred"
        )
        self.record_button.pack(pady=10)
        
        self.finish_button = ctk.CTkButton(
            self.frame,
            text="⏹️ Finalizar (F11)",
            command=self.finish_recording
        )
        self.finish_button.pack(pady=10)
        
        # Novo: Widget de logs minimalista
        self.log_textbox = ctk.CTkTextbox(self.frame, width=350, height=100)
        self.log_textbox.configure(state="disabled")  # Impede edição manual
        self.log_textbox.pack(pady=10)
        
        # 4. Variáveis de controle
        self.total_elapsed = timedelta()
        self.pause_time = None
        self.is_paused = False
        
        # 5. Atalhos de teclado
        keyboard.add_hotkey('F9', self.toggle_recording)
        keyboard.add_hotkey('F11', self.finish_recording)
        
        # 6. Inicialização dos atualizadores periódicos
        self.update_timer()
        self.check_messages()
        self.update_status_display()
    
    def add_log(self, message):
        """Adiciona uma mensagem de log com timestamp na área de logs."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"{timestamp} - {message}\n"
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", log_message)
        self.log_textbox.configure(state="disabled")
        self.log_textbox.see("end")  # Rola para o final
    
    def update_status_display(self):
        """Atualiza os indicadores visuais de status."""
        global is_recording, audio_segments
        
        if is_recording and not self.is_paused:
            self.recording_indicator.configure(text_color="red")
        else:
            self.recording_indicator.configure(text_color="gray")
        
        self.segments_label.configure(text=f"Segmentos gravados: {len(audio_segments)}")
        self.root.after(100, self.update_status_display)
    
    def check_messages(self):
        """Verifica mensagens da thread de processamento."""
        try:
            while True:
                message = message_queue.get_nowait()
                if message.get('type') == 'status':
                    self.update_status_text(message['text'])
                elif message.get('type') == 'finish':
                    self.root.after(2000, self.root.destroy)
        except queue.Empty:
            pass
        self.root.after(100, self.check_messages)
    
    def update_timer(self):
        """Atualiza o timer na interface."""
        global start_time, is_recording
        if is_recording and start_time and not self.is_paused:
            current_time = datetime.now()
            current_elapsed = current_time - start_time
            self.time_label.configure(text=str(self.total_elapsed + current_elapsed).split('.')[0])
        self.root.after(100, self.update_timer)
    
    def format_status_message(self, message):
        """Formata mensagens longas para exibição adequada."""
        max_chars = 40
        words = message.split()
        lines = []
        current_line = []
        for word in words:
            if sum(len(w) for w in current_line) + len(current_line) + len(word) > max_chars:
                lines.append(' '.join(current_line))
                current_line = [word]
            else:
                current_line.append(word)
        if current_line:
            lines.append(' '.join(current_line))
        return '\n'.join(lines)
    
    def update_status_text(self, message):
        """Atualiza o texto de status com formatação adequada."""
        formatted_message = self.format_status_message(message)
        self.status_label.configure(text=formatted_message)
    
    # Método para aprimorar o texto com GPT-4-turbo (já implementado anteriormente)
    def aprimorar_texto(self, texto):
        """Aprimora o texto bruto do Whisper usando GPT"""
        client = OpenAI(api_key=OPENAI_API_KEY)
        prompt = (
            "Reescreva o seguinte texto transcrito de uma gravação de voz, corrigindo erros, adicionando pontuação "
            "e tornando a leitura mais fluida:\n\n"
            f"{texto}"
        )
        resposta = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return resposta.choices[0].message.content.strip()
    
    # Controle da gravação
    def toggle_recording(self):
        global stream, is_recording, start_time
        if not is_recording:
            is_recording = True
            self.is_paused = False
            if start_time is None:
                start_time = datetime.now()
                self.total_elapsed = timedelta()
                self.update_status_text("Iniciando nova gravação...")
            else:
                start_time = datetime.now()
                self.update_status_text("Retomando gravação...")
            stream = sd.InputStream(
                samplerate=FS,
                channels=1,
                dtype='int16',
                callback=audio_callback
            )
            stream.start()
            self.record_button.configure(
                text="⏸️ Pausar (F9)",
                fg_color="orange",
                hover_color="#b37400"
            )
        else:
            is_recording = False
            self.is_paused = True
            if start_time:
                self.total_elapsed += datetime.now() - start_time
            if stream is not None:
                stream.stop()
                stream.close()
                stream = None
            self.record_button.configure(
                text="▶️ Continuar (F9)",
                fg_color="red",
                hover_color="#8b0000"
            )
            self.update_status_text("Gravação pausada - F9 para continuar, F11 para finalizar")
    
    def finish_recording(self):
        """Finaliza a gravação e processa o áudio."""
        global finish, is_recording, stream
        if is_recording and stream is not None:
            stream.stop()
            stream.close()
            stream = None
            is_recording = False
        finish = True
        self.update_status_text("Processando gravação...")
        self.add_log("Processando gravação...")
        self.root.after(100, self.process_audio)
    
    def process_audio(self):
        """Processa o áudio gravado e obtém a transcrição."""
        if audio_segments:
            self.add_log("Enviando áudio")
            audio_data = np.concatenate(audio_segments, axis=0)
            sf.write(ARQUIVO_AUDIO, audio_data, FS)
            self.update_status_text("Transcrevendo áudio...")
            threading.Thread(target=self.transcribe_audio).start()
        else:
            self.update_status_text("Nenhum áudio gravado")
            self.root.after(2000, self.root.destroy)
    
    def transcribe_audio(self):
        """Transcreve o áudio e melhora o texto antes de copiar."""
        client = OpenAI(api_key=OPENAI_API_KEY)
        try:
            self.add_log("Transcrevendo")
            with open(ARQUIVO_AUDIO, "rb") as audio_file:
                resposta = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file
                )
            transcricao_bruta = resposta.text.strip()
            self.add_log("Aprimorando o texto")
            transcricao_aprimorada = self.aprimorar_texto(transcricao_bruta)
            pyperclip.copy(transcricao_aprimorada)
            message_queue.put({
                'type': 'status',
                'text': 'Transcrição formatada e copiada para a área de transferência!'
            })
            message_queue.put({'type': 'finish'})
        except Exception as e:
            message_queue.put({
                'type': 'status',
                'text': f'Erro na transcrição: {str(e)}'
            })

def audio_callback(indata, frames, time_info, status):
    """Callback para processar o áudio recebido."""
    if status:
        print(status)
    audio_segments.append(indata.copy())

if __name__ == "__main__":
    app = GravadorWidget()
    app.root.mainloop()
