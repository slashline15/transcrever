import sounddevice as sd
import soundfile as sf
import numpy as np
from openai import OpenAI
import pyperclip
import keyboard
from dotenv import load_dotenv
import time
import os

load_dotenv()

# Configurações
FS = 16000                           # frequência de amostragem
ARQUIVO_AUDIO = "gravacao.wav"       # Nome do arquivo de áudio


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# load_dotenv("OPENAI_API_KEY")

# Variáveis globais
audio_segments = []     # Armazena os pedaços de áudio gravados
stream = None           # Referência para o stream de áudio
is_recording = False    # Flag para indicar se está gravando
finish = False          # Flag para finalizar a gravação


# Inicializa o cliente OpenAI
client = OpenAI(api_key=OPENAI_API_KEY)


# Grava o áudio
# print(f"Gravando por {DURACAO} segundos... Fala aí, Daniel!")
# audio = sd.rec(int(DURACAO * FS), samplerate=FS, channels=1, dtype='int16')
# sd.wait()
# sf.write(ARQUIVO_AUDIO, audio, FS)
# print("Gravação finalizada!")


# Callback do stream: adiciona os dados gravados à lista
def audio_callback(indata, frames, time_info, status):
    if status:
        print(status)
    audio_segments.append(indata.copy())


# Função para iniciar ou retomar a gravação
def start_recording():
    global stream, is_recording
    if not is_recording:
        print("Gravação iniciada ou retomada!")
        is_recording = True
        stream = sd.InputStream(samplerate=FS, channels=1, dtype='int16', callback=audio_callback)
        stream.start()

# Função para pausar a gravação
def pause_recording():
    global stream, is_recording
    if is_recording:
        print("Gravação pausada!")
        is_recording = False
        if stream is not None:
            stream.stop()
            stream.close()
            stream = None

# Função para finalizar a gravação
def finish_recording():
    global finish, is_recording, stream
    print("Finalizando gravação!")
    if is_recording and stream is not None:
        stream.stop()
        stream.close()
        stream = None
        is_recording = False
    finish = True
    
# Registra os atalhos
keyboard.add_hotkey('F9', start_recording)
keyboard.add_hotkey('F10', pause_recording)
keyboard.add_hotkey('F11', finish_recording)

print("Instruções:")
print("→ Pressione F9 para iniciar ou retomar a gravação.")
print("→ Pressione F10 para pausar a gravação.")
print("→ Pressione F11 para finalizar a gravação.")

# Loop aguardando o comando de finalizar (F11)
while not finish:
    time.sleep(0.1)
    
# Salva o áudio se tiver gravado alguma coisa
if audio_segments:
    audio_data = np.concatenate(audio_segments, axis=0)
    sf.write(ARQUIVO_AUDIO, audio_data, FS)
    print(f"Áudio salvo em '{ARQUIVO_AUDIO}'")
else:
    print("Nenhum áudio gravado.")
    exit()


# Envia o áudio para a API do Whisper e obtém a transcrição
with open(ARQUIVO_AUDIO, "rb") as audio_file:
    print("Transcrevendo com o Whisper...")
    resposta = client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file
    )

# Na nova versão, a resposta já é o texto diretamente
transcricao = resposta.text.strip()
print("Transcrição:")
print(transcricao)

# Copia a transcrição para a área de transferência
pyperclip.copy(transcricao)
print("Transcrição copiada para a área de transferência!")