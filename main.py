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

class GravadorWidget:
    def __init__(self):
        # configuração da janela principal
        self.root = ctk.CTk()
        self.root.title("Gravador de Áudio")
        self.root.geometry("400x300")
        
        # Crição dos elementos da interface
        self.frame = ctk.CTkFrame(self.root)
        self.frame.pack(pady=20, padx=20, fill="both", expand=True)
        
        # Label para mostrar o tempo de gravação
        self.time_label = ctk.CTkLabel(self.frame,
                                      text="00:00:00",
                                      font=("Arial", 24))
        self.time_label.pack(pady=20)
        
        # Botões de controle
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
        
        # Label de status
        self.status_label = ctk.CTkLabel(
            self.frame,
            text="Pronto para gravar"
        )
        
        # Inicializa o temporizador
        self.update_timer()
        
        # Registra os atalhos do teclado
        keyboard.add_hotkey('F9', self.toggle_recording)
        keyboard.add_hotkey('F11', self.finish_recording)
        
    def update_timer(self):
        """Atualiza o timer na interface"""
        global start_time, is_recording
        
        if is_recording and start_time:
            elapsed_time = datetime.now() - start_time
            # Remove microssegundos da exibição
            elapsed_str = str(elapsed_time).split('.')[0]
            self.time_label.configure(text=elapsed_str)
            
        # Agenda a próxima atualização
        self.root.after(1000, self.update_timer)
        
    def toggle_recording(self):
        """Alterna entre iniciar e pausar a gravação"""
        global stream, is_recording, start_time
        
        if not is_recording:
            # Inicia a gravação
            is_recording = True
            if start_time is None:
                start_time = datetime.now()
            stream = sd.InputStream(
                samplerate=FS, 
                channels=1, 
                dtype='int16', 
                callback=audio_callback
            )
            stream.start()
            self.record_button.configure(text="Pausar (F9)", fg_color="orange")
            self.status_label.configure(text="Gravando...")
        else:
            # Pausa a gravação
            is_recording = False
            if stream is not None:
                stream.stop()
                stream.close()
                stream = None
            self.record_button.configure(text="Continuar (F9)", fg_color="red")
            self.status_label.configure(text="Pausado")
            
    def finish_recording(self):
        """Finaliza a gravação e processa o áudio"""
        global finish, is_recording, stream
        
        if is_recording and stream is not None:
            stream.stop()
            stream.close()
            stream = None
            is_recording = False
        
        finish = True
        self.status_label.configure(text="Processando gravação...")
        self.root.after(100, self.process_audio)
        
    def process_audio(self):
        """Processa o áudio gravado e obtém a transcrição"""
        # Salva o áudio se tiver gravado alguma coisa
        if audio_segments:
            audio_data = np.concatenate(audio_segments, axis=0)
            sf.write(ARQUIVO_AUDIO, audio_data, FS)
            self.status_label.configure(text="Transcrevendo áudio...")
            
            # Inicia a transcrição em uma thread separada
            threading.Thread(target=self.transcribe_audio).start()
        else:
            self.status_label.configure(text="Nenhum áudio gravado")
            self.root.after(2000, self.root.destroy)

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
            
            # Atualiza a interface na thread principal
            self.root.after(0, lambda: self.status_label.configure(
                text="Transcrição copiada para a área de transferência!"
            ))
            self.root.after(2000, self.root.destroy)
            
        except Exception as e:
            self.root.after(0, lambda: self.status_label.configure(
                text=f"Erro na transcrição: {str(e)}"
            ))
            

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