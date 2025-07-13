"""
Módulo core para captura de áudio com thread-safety adequado.
Sprint 0: Separação de responsabilidades e proteção de dados.
"""

import sounddevice as sd
import soundfile as sf
import numpy as np
from datetime import datetime
import threading
import queue
import os
from dataclasses import dataclass
from typing import Optional, Callable
from collections import deque
import tempfile

@dataclass
class AudioSegment:
    """Representa um segmento de áudio com metadados."""
    data: np.ndarray
    timestamp: datetime
    duration: float

class AudioRecorder:
    """Gerenciador de gravação de áudio thread-safe."""
    
    def __init__(self, sample_rate: int = 16000, channels: int = 1):
        self.sample_rate = sample_rate
        self.channels = channels
        self.dtype = 'int16'
        
        # Thread-safety
        self._lock = threading.Lock()
        self._audio_queue = queue.Queue(maxsize=1000)  # Limita memória
        self._is_recording = False
        self._stream: Optional[sd.InputStream] = None
        
        # Arquivo temporário para gravações longas
        self._temp_file = None
        self._wave_writer = None
        
        # Callbacks
        self._status_callback: Optional[Callable] = None
        
        # Estatísticas
        self._start_time: Optional[datetime] = None
        self._segments_count = 0
        self._total_duration = 0.0
        
    def set_status_callback(self, callback: Callable[[str], None]):
        """Define callback para mudanças de status."""
        self._status_callback = callback
        
    def _notify_status(self, status: str):
        """Notifica mudança de status se callback definido."""
        if self._status_callback:
            self._status_callback(status)
    
    def _audio_callback(self, indata, frames, time_info, status):
        """Callback thread-safe para processar áudio."""
        if status:
            print(f"Audio status: {status}")
            
        if self._is_recording:
            try:
                # Cria cópia para evitar problemas de memória
                audio_copy = indata.copy()
                
                # Usa put_nowait para não bloquear thread de áudio
                self._audio_queue.put_nowait(AudioSegment(
                    data=audio_copy,
                    timestamp=datetime.now(),
                    duration=len(audio_copy) / self.sample_rate
                ))
                
            except queue.Full:
                print("WARNING: Audio queue full, dropping frames")
            except Exception as e:
                print(f"ERROR in audio callback: {e}")
    
    def start_recording(self) -> bool:
        """Inicia gravação com proteção thread-safe."""
        with self._lock:
            if self._is_recording:
                return False
                
            try:
                # Cria arquivo temporário para gravação
                self._temp_file = tempfile.NamedTemporaryFile(
                    suffix='.wav', 
                    delete=False
                )
                self._wave_writer = sf.SoundFile(
                    self._temp_file.name,
                    mode='w',
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    format='WAV',
                    subtype='PCM_16'
                )
                
                # Inicia stream
                self._stream = sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    dtype=self.dtype,
                    callback=self._audio_callback,
                    blocksize=2048  # Otimizado para latência
                )
                self._stream.start()
                
                self._is_recording = True
                self._start_time = datetime.now()
                self._segments_count = 0
                
                # Inicia thread para processar fila
                self._processor_thread = threading.Thread(
                    target=self._process_audio_queue,
                    daemon=True
                )
                self._processor_thread.start()
                
                self._notify_status("recording_started")
                return True
                
            except Exception as e:
                print(f"Failed to start recording: {e}")
                self._cleanup()
                return False
    
    def _process_audio_queue(self):
        """Processa fila de áudio e salva em disco."""
        while self._is_recording or not self._audio_queue.empty():
            try:
                # Timeout para não travar quando parar
                segment = self._audio_queue.get(timeout=0.1)
                
                # Salva no arquivo temporário
                if self._wave_writer:
                    self._wave_writer.write(segment.data.flatten())
                    self._segments_count += 1
                    self._total_duration += segment.duration
                    
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error processing audio: {e}")
    
    def pause_recording(self) -> bool:
        """Pausa gravação mantendo dados."""
        with self._lock:
            if not self._is_recording:
                return False
                
            self._is_recording = False
            
            if self._stream:
                self._stream.stop()
                self._stream.close()
                self._stream = None
                
            self._notify_status("recording_paused")
            return True
    
    def resume_recording(self) -> bool:
        """Retoma gravação no mesmo arquivo."""
        with self._lock:
            if self._is_recording:
                return False
                
            try:
                # Reabre stream mas mantém arquivo
                self._stream = sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    dtype=self.dtype,
                    callback=self._audio_callback,
                    blocksize=2048
                )
                self._stream.start()
                self._is_recording = True
                
                self._notify_status("recording_resumed")
                return True
                
            except Exception as e:
                print(f"Failed to resume recording: {e}")
                return False
    
    def stop_recording(self) -> Optional[str]:
        """Para gravação e retorna caminho do arquivo."""
        with self._lock:
            if not self._wave_writer:
                return None
                
            self._is_recording = False
            
            # Para stream se ainda estiver rodando
            if self._stream:
                self._stream.stop()
                self._stream.close()
                self._stream = None
            
            # Aguarda processamento da fila
            while not self._audio_queue.empty():
                threading.Event().wait(0.01)
            
            # Fecha arquivo
            self._wave_writer.close()
            self._wave_writer = None
            
            temp_path = self._temp_file.name
            self._temp_file = None
            
            self._notify_status("recording_stopped")
            
            return temp_path
    
    def _cleanup(self):
        """Limpa recursos em caso de erro."""
        self._is_recording = False
        
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except:
                pass
            self._stream = None
            
        if self._wave_writer:
            try:
                self._wave_writer.close()
            except:
                pass
            self._wave_writer = None
            
        if self._temp_file:
            try:
                os.unlink(self._temp_file.name)
            except:
                pass
            self._temp_file = None
    
    @property
    def is_recording(self) -> bool:
        """Retorna status de gravação thread-safe."""
        with self._lock:
            return self._is_recording
    
    @property
    def recording_stats(self) -> dict:
        """Retorna estatísticas da gravação atual."""
        with self._lock:
            if not self._start_time:
                return {
                    "duration": 0,
                    "segments": 0,
                    "status": "idle"
                }
                
            duration = (datetime.now() - self._start_time).total_seconds()
            return {
                "duration": duration,
                "segments": self._segments_count,
                "status": "recording" if self._is_recording else "paused",
                "queue_size": self._audio_queue.qsize()
            }
            
    def __del__(self):
        """Garante limpeza ao destruir objeto."""
        self._cleanup()