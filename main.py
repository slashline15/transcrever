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
FS = 16000                                        # frequência de amostragem
ARQUIVO_AUDIO = "gravacao.wav"                    # Nome do arquivo de áudio
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")      # Chave da OpenaAi

# Variáveis globais
audio_segments = []     # Armazena os pedaços de áudio gravados
stream = None           # Referência para o stream de áudio
is_recording = False    # Flag para indicar se está gravando
finish = False          # Flag para finalizar a gravação
start_time = None       # Tempo de início da gravação
# Fila para comunicação entre threads
message_queue = queue.Queue()

class GravadorWidget:
    def __init__(self):
        # 1. Configuração inicial da janela
        self.root = ctk.CTk()
        self.root.title("Gravador de Áudio")
        self.root.geometry("400x300")
        
        # 2. Criação do frame principal
        self.frame = ctk.CTkFrame(self.root)
        self.frame.pack(pady=20, padx=20, fill="both", expand=True)
        
        # 3. Criação de TODOS os elementos visuais
        # Timer
        self.time_label = ctk.CTkLabel(self.frame, text="00:00:00", font=("Arial", 24))
        self.time_label.pack(pady=20)
        
        # Indicador de gravação (bolinha)
        self.recording_indicator = ctk.CTkLabel(
        self.frame,
        text="●",
        font=("Arial", 24),
        text_color="gray"
        )
        self.recording_indicator.pack(pady=5)
        
        # Botões
        self.record_button = ctk.CTkButton(
            self.frame,
            text="Gravar (F9)",
            command=self.toggle_recording,
            fg_color="red",
            hover_color="darkred"
        )
        self.record_button.pack(pady=10)
        
        self.finish_button = ctk.CTkButton(
            self.frame,
            text="Finalizar (F11)",
            command=self.finish_recording
        )
        self.finish_button.pack(pady=10)
        
        # 4. Inicialização de variáveis de controle
        self.total_elapsed = timedelta()  # Tempo total acumulado
        self.pause_time = None            # Momento em que pausou
        self.is_paused = False           # Estado de pausa
        
        # 5. Inicialização dos atualizadores periódicos
        self.update_timer()
        self.check_messages()
        self.update_status_display()
        
        # 6. Configuração dos atalhos de teclado
        keyboard.add_hotkey('F9', self.toggle_recording)
        keyboard.add_hotkey('F11', self.finish_recording)
        
        # Status e contador de segmentos
        self.status_label = ctk.CTkLabel(self.frame, text="Pronto para gravar")
        self.status_label.pack(pady=10)
        
        # self.segments_label = ctk.CTkLabel(
        #     self.frame,
        #     text="Segmentos gravados: 0",
        #     font=("Arial", 12)
        # )
        # self.segments_label.pack(pady=5)
        
        
        # # Label de status
        # self.status_label = ctk.CTkLabel(self.frame, text="Pronto para gravar")
        # self.status_label.pack(pady=10)
        
        # # Inicializa o temporizador e o verificador de mensagens
        # self.update_timer()
        # self.check_messages()
        # self.update_status_display()  # Adicionar esta linha
        # self.total_elapsed = timedelta()  # Tempo total acumulado
        # self.pause_time = None            # Momento em que pausou
        # self.is_paused = False           # Estado de pausa
        
        # # Adicione um indicador visual de status mais detalhado
        # self.recording_indicator = ctk.CTkLabel(
        #     self.frame,
        #     text="●",  # Ponto que servirá como indicador
        #     font=("Arial", 24),
        #     text_color="gray"  # Começa cinza
        # )
        # self.recording_indicator.pack(pady=5)
        
        # # Adicione um contador de segmentos
        # self.segments_label = ctk.CTkLabel(
        #     self.frame,
        #     text="Segmentos gravados: 0",
        #     font=("Arial", 12)
        # )
        # self.segments_label.pack(pady=5)
        
        # # Registra os atalhos de teclado
        # keyboard.add_hotkey('F9', self.toggle_recording)
        # keyboard.add_hotkey('F11', self.finish_recording)

    def update_status_display(self):
        """Atualiza os indicadores visuais de status"""
        global is_recording, audio_segments
        
        if is_recording:
            self.recording_indicator.configure(text_color="red")
            self.segments_label.configure(
                text=f"Segmentos gravados: {len(audio_segments)}"
            )
        else:
            self.recording_indicator.configure(text_color="gray")
        
        # Atualiza a cada 100ms para ser mais responsivo
        self.root.after(100, self.update_status_display)

    def check_messages(self):
        """Verifica mensagens da thread de processamento"""
        try:
            # Verifica se há mensagens na fila (não bloqueia)
            while True:
                message = message_queue.get_nowait()
                if message.get('type') == 'status':
                    self.status_label.configure(text=message['text'])
                elif message.get('type') == 'finish':
                    self.root.after(2000, self.root.destroy)
        except queue.Empty:
            pass
        
        # Agenda próxima verificação
        self.root.after(100, self.check_messages)

    def update_timer(self):
        """Atualiza o timer na interface"""
        global start_time, is_recording
        
        if is_recording and start_time:
            current_time = datetime.now()
            if not self.is_paused:
                # Calcula o tempo decorrido desde o início ou retomada
                current_elapsed = current_time - start_time
                # Adiciona ao tempo total acumulado
                self.time_label.configure(text=str(self.total_elapsed + current_elapsed).split('.')[0])
            # else:
            #     self.total_elapsed += current_time - start_time
            # start_time = current_time
            # elapsed_time = datetime.now() - start_time
            # elapsed_str = str(elapsed_time).split('.')[0]
            # self.time_label.configure(text=elapsed_str)
        
        self.root.after(100, self.update_timer) # Atualiza a cada 100ms para maior precisão

    def toggle_recording(self):
        """Função melhorada para alternar a gravação"""
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
                self.status_label.configure(text="Retomando gravação...")
            
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
            
        else:  # Pausando gravação
            is_recording = False
            self.is_paused = True
            
            # Calcula e acumula o tempo até a pausa
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
            self.update_status_text("Gravação pausada - Pressione F9 para continuar ou F11 para finalizar")
            
    def finish_recording(self):
        """Finaliza a gravação e processa o áudio"""
        global finish, is_recording, stream
        
        if is_recording and stream is not None:
            stream.stop()
            stream.close()
            stream = None
            is_recording = False
        
        finish = True
        message_queue.put({'type': 'status', 'text': 'Processando gravação...'})
        self.root.after(100, self.process_audio)

    def process_audio(self):
        """Processa o áudio gravado e obtém a transcrição"""
        if audio_segments:
            audio_data = np.concatenate(audio_segments, axis=0)
            sf.write(ARQUIVO_AUDIO, audio_data, FS)
            message_queue.put({'type': 'status', 'text': 'Transcrevendo áudio...'})
            
            # Inicia a transcrição em uma thread separada
            threading.Thread(target=self.transcribe_audio).start()
        else:
            message_queue.put({'type': 'status', 'text': 'Nenhum áudio gravado'})
            message_queue.put({'type': 'finish'})

    def transcribe_audio(self):
        """Transcreve o áudio usando a API do Whisper"""
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        try:
            with open(ARQUIVO_AUDIO, "rb") as audio_file:
                resposta = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file
                )
            
            transcricao = resposta.text.strip()
            pyperclip.copy(transcricao)
            
            message_queue.put({
                'type': 'status',
                'text': 'Transcrição copiada para a área de transferência!'
            })
            message_queue.put({'type': 'finish'})
            
        except Exception as e:
            message_queue.put({
                'type': 'status',
                'text': f'Erro na transcrição: {str(e)}'
            })
            
    def format_status_message(self, message):
        """Formata mensagens longas para exibição adequada"""
        max_chars = 40  # Número máximo de caracteres por linha
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
        """Atualiza o texto de status com formatação adequada"""
        formatted_message = self.format_status_message(message)
        self.status_label.configure(text=formatted_message)

def audio_callback(indata, frames, time_info, status):
    """Callback para processar o áudio recebido"""
    if status:
        print(status)
    audio_segments.append(indata.copy())

# Inicializa e executa a interface
if __name__ == "__main__":
    app = GravadorWidget()
    app.root.mainloop()

# # Inicializa o cliente OpenAI
# client = OpenAI(api_key=OPENAI_API_KEY)


# # Grava o áudio
# # print(f"Gravando por {DURACAO} segundos... Fala aí, Daniel!")
# # audio = sd.rec(int(DURACAO * FS), samplerate=FS, channels=1, dtype='int16')
# # sd.wait()
# # sf.write(ARQUIVO_AUDIO, audio, FS)
# # print("Gravação finalizada!")


# # Callback do stream: adiciona os dados gravados à lista
# def audio_callback(indata, frames, time_info, status):
#     if status:
#         print(status)
#     audio_segments.append(indata.copy())


# # Função para iniciar ou retomar a gravação
# def start_recording():
#     global stream, is_recording
#     if not is_recording:
#         print("Gravação iniciada ou retomada!")
#         is_recording = True
#         stream = sd.InputStream(samplerate=FS, channels=1, dtype='int16', callback=audio_callback)
#         stream.start()

# # Função para pausar a gravação
# def pause_recording():
#     global stream, is_recording
#     if is_recording:
#         print("Gravação pausada!")
#         is_recording = False
#         if stream is not None:
#             stream.stop()
#             stream.close()
#             stream = None

# # Função para finalizar a gravação
# def finish_recording():
#     global finish, is_recording, stream
#     print("Finalizando gravação!")
#     if is_recording and stream is not None:
#         stream.stop()
#         stream.close()
#         stream = None
#         is_recording = False
#     finish = True
    
# # Registra os atalhos
# keyboard.add_hotkey('F9', start_recording)
# keyboard.add_hotkey('F10', pause_recording)
# keyboard.add_hotkey('F11', finish_recording)

# print("Instruções:")
# print("→ Pressione F9 para iniciar ou retomar a gravação.")
# print("→ Pressione F10 para pausar a gravação.")
# print("→ Pressione F11 para finalizar a gravação.")

# # Loop aguardando o comando de finalizar (F11)
# while not finish:
#     time.sleep(0.1)
    
# # Salva o áudio se tiver gravado alguma coisa
# if audio_segments:
#     audio_data = np.concatenate(audio_segments, axis=0)
#     sf.write(ARQUIVO_AUDIO, audio_data, FS)
#     print(f"Áudio salvo em '{ARQUIVO_AUDIO}'")
# else:
#     print("Nenhum áudio gravado.")
#     exit()


# # Envia o áudio para a API do Whisper e obtém a transcrição
# with open(ARQUIVO_AUDIO, "rb") as audio_file:
#     print("Transcrevendo com o Whisper...")
#     resposta = client.audio.transcriptions.create(
#         model="whisper-1",
#         file=audio_file
#     )

# # Na nova versão, a resposta já é o texto diretamente
# transcricao = resposta.text.strip()
# print("Transcrição:")
# print(transcricao)

# # Copia a transcrição para a área de transferência
# pyperclip.copy(transcricao)
# print("Transcrição copiada para a área de transferência!")