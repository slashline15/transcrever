"""
Teste de stress para verificar se as correções funcionam
Rode isso ANTES de tentar a UI completa
"""

import time
import os
from audio_core import AudioRecorder

def test_basic_recording():
    """Testa gravação básica sem travamentos."""
    print("🧪 Teste 1: Gravação básica")
    
    recorder = AudioRecorder()
    
    # Grava 2 segundos
    print("▶️  Iniciando gravação...")
    assert recorder.start_recording(), "Falha ao iniciar"
    
    time.sleep(2)
    
    # Para e pega arquivo
    print("⏹️  Parando gravação...")
    audio_file = recorder.stop_recording()
    
    assert audio_file is not None, "Nenhum arquivo retornado"
    assert os.path.exists(audio_file), "Arquivo não existe"
    
    # Verifica tamanho (deve ter ~64KB para 2s @ 16kHz mono)
    size = os.path.getsize(audio_file)
    print(f"✅ Arquivo criado: {size} bytes")
    
    # Limpa
    os.unlink(audio_file)
    return True

def test_pause_resume():
    """Testa pause/resume."""
    print("\n🧪 Teste 2: Pause/Resume")
    
    recorder = AudioRecorder()
    
    # Grava
    recorder.start_recording()
    time.sleep(1)
    
    # Pausa
    print("⏸️  Pausando...")
    assert recorder.pause_recording(), "Falha ao pausar"
    stats = recorder.recording_stats
    assert stats['status'] == 'paused'
    
    time.sleep(1)
    
    # Resume
    print("▶️  Resumindo...")
    assert recorder.resume_recording(), "Falha ao resumir"
    stats = recorder.recording_stats
    assert stats['status'] == 'recording'
    
    time.sleep(1)
    
    # Para
    audio_file = recorder.stop_recording()
    assert audio_file is not None
    
    os.unlink(audio_file)
    return True

def test_multiple_sessions():
    """Testa múltiplas gravações sem travamento."""
    print("\n🧪 Teste 3: Múltiplas sessões")
    
    recorder = AudioRecorder()
    
    for i in range(5):
        print(f"\n📍 Sessão {i+1}/5")
        
        # Inicia
        assert recorder.start_recording(), f"Falha na sessão {i+1}"
        
        # Grava 1 segundo
        time.sleep(1)
        
        # Verifica stats
        stats = recorder.recording_stats
        print(f"   Duration: {stats['duration']:.1f}s")
        print(f"   Queue: {stats['queue_size']}")
        print(f"   Dropped: {stats['dropped_frames']}")
        
        # Para
        audio_file = recorder.stop_recording()
        assert audio_file is not None
        
        # Limpa
        os.unlink(audio_file)
        
        # Pequena pausa entre sessões
        time.sleep(0.5)
    
    print("\n✅ Todas as sessões OK!")
    return True

def test_long_recording():
    """Testa gravação longa para verificar memória."""
    print("\n🧪 Teste 4: Gravação longa (10s)")
    
    recorder = AudioRecorder()
    recorder.start_recording()
    
    # Monitora por 10 segundos
    for i in range(10):
        time.sleep(1)
        stats = recorder.recording_stats
        print(f"⏱️  {i+1}s - Queue: {stats['queue_size']}, Dropped: {stats['dropped_frames']}")
    
    audio_file = recorder.stop_recording()
    
    if audio_file:
        size_mb = os.path.getsize(audio_file) / 1024 / 1024
        print(f"✅ Arquivo final: {size_mb:.2f} MB")
        os.unlink(audio_file)
    
    return True

if __name__ == "__main__":
    print("🚀 Iniciando testes do audio_core corrigido\n")
    
    try:
        test_basic_recording()
        test_pause_resume()
        test_multiple_sessions()
        test_long_recording()
        
        print("\n🎉 TODOS OS TESTES PASSARAM!")
        print("✅ O core está funcionando. Pode testar a UI.")
        
    except AssertionError as e:
        print(f"\n❌ TESTE FALHOU: {e}")
    except Exception as e:
        print(f"\n💥 ERRO INESPERADO: {e}")
        import traceback
        traceback.print_exc()