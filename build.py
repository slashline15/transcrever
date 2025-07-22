# python build.py

"""
Script de build para Gravador de Áudio v2
Gera executável com todos os módulos
"""

import PyInstaller.__main__
import os
import shutil

# Limpa builds anteriores
for folder in ['build', 'dist']:
    if os.path.exists(folder):
        shutil.rmtree(folder)
        print(f"✅ Pasta {folder} removida")

# Cria ícone se não existir
if not os.path.exists('icon.ico'):
    from PIL import Image, ImageDraw
    img = Image.new('RGB', (64, 64), color='blue')
    d = ImageDraw.Draw(img)
    d.ellipse([10, 10, 54, 54], fill='white')
    d.ellipse([20, 20, 44, 44], fill='red')
    img.save('icon.ico')
    print("✅ Ícone criado")

# Verifica se os módulos existem
required_files = ['main.py', 'audio_core.py', 'storage.py', '.env']
missing = [f for f in required_files if not os.path.exists(f)]

if missing:
    print(f"❌ Arquivos faltando: {', '.join(missing)}")
    print("Certifique-se de ter todos os arquivos necessários!")
    exit(1)

print("🔨 Iniciando build...")

# Configuração do PyInstaller
PyInstaller.__main__.run([
    'main.py',
    '--name=AudioTranscriber_v2',
    '--onefile',
    '--windowed',
    '--icon=icon.ico',
    
    # Inclui arquivos de dados
    '--add-data=.env;.',
    '--add-data=audio_core.py;.',
    '--add-data=storage.py;.',
    
    # Hidden imports necessários
    '--hidden-import=pystray._win32',
    '--hidden-import=customtkinter',
    '--hidden-import=plyer.platforms.win.notification',
    '--hidden-import=sqlite3',
    '--hidden-import=sounddevice',
    '--hidden-import=soundfile',
    
    # Coleta todos os dados do customtkinter
    '--collect-all=customtkinter',
    
    # Outras opções
    '--noconfirm',
    '--clean',
    
    # Otimizações
    '--optimize=2',
])

print("\n✅ Build concluído!")
print(f"📁 Executável em: dist/AudioTranscriber_v2.exe")
print("\nPróximos passos:")
print("1. Teste o executável")
print("2. Verifique se o .env está na mesma pasta")
print("3. Distribua para uso!")

# Cria um .bat para facilitar execução com console (debug)
with open('dist/AudioTranscriber_v2_DEBUG.bat', 'w') as f:
    f.write('@echo off\n')
    f.write('AudioTranscriber_v2.exe\n')
    f.write('pause\n')
    
print("\n💡 Dica: Use AudioTranscriber_v2_DEBUG.bat para ver logs de erro")