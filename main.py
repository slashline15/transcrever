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
DURACAO = 10           # duração da gravação em segundos
FS = 16000            # frequência de amostragem
ARQUIVO_AUDIO = "gravacao.wav"


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# load_dotenv("OPENAI_API_KEY")


# Inicializa o cliente OpenAI
client = OpenAI(api_key=OPENAI_API_KEY)
# Sua API key



# Grava o áudio
print(f"Gravando por {DURACAO} segundos... Fala aí, Daniel!")
audio = sd.rec(int(DURACAO * FS), samplerate=FS, channels=1, dtype='int16')
sd.wait()
sf.write(ARQUIVO_AUDIO, audio, FS)
print("Gravação finalizada!")

# Transcrição com o novo endpoint da API do Whisper
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