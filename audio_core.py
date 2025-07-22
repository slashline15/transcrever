"""
Módulo core para captura de áudio com thread-safety adequado.
Sprint 0: Separação de responsabilidades e proteção de dados.
VERSÃO CORRIGIDA - sem travas, sem vazamento de memória
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
import tempfile
import time

@dataclass
class AudioSegment:
    """Representa um segmento de áudio com metadados."""
    data: np.ndarray
    timestamp: datetime
    duration: float

class AudioRecorder:
    """Gerenciador de gravação de áudio thread-safe."""
    
    MAX_QUEUE_SIZE = 200  # ~10 segundos de áudio
    
    def __init__(self, sample_rate: int = 16000, channels: int = 1):
        self.sample_rate = sample_rate
        self.channels = channels
        self.dtype = 'int16'
        
        # Thread-safety
        self._lock = threading.Lock()
        self._audio_queue: queue.Queue = queue.Queue(maxsize=self.MAX_QUEUE_SIZE)
        self._is_recording = False
        self._is_paused = False
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
        self._dropped_frames = 0
        
        # Thread de processamento
        self._processor_thread: Optional[threading.Thread] = None
        self._processor_running = False
        
    def set_status_callback(self, callback: Callable[[str], None]):
        """Define callback para mudanças de status."""
        self._status_callback = callback
        
    def _notify_status(self, status: str):
        """Notifica mudança de status se callback definido."""
        if self._status_callback:
            try:
                self._status_callback(status)
            except Exception as e:
                print(f"Error in status callback: {e}")
    
    def _audio_callback(self, indata, frames, time_info, status):
        """Callback thread-safe para processar áudio."""
        # CRÍTICO: Sai imediatamente se não está gravando
        if not self._is_recording or self._is_paused:
            return
            
        if status:
            print(f"Audio status: {status}")
            
        try:
            # Cria cópia para evitar problemas de memória
            audio_copy = indata.copy()
            
            # Back-pressure: descarta se fila cheia
            try:
                self._audio_queue.put_nowait(AudioSegment(
                    data=audio_copy,
                    timestamp=datetime.now(),
                    duration=len(audio_copy) / self.sample_rate
                ))
            except queue.Full:
                self._dropped_frames += 1
                if self._dropped_frames % 100 == 0:  # Log a cada 100 drops
                    print(f"WARNING: Dropped {self._dropped_frames} frames")
                    
        except Exception as e:
            print(f"ERROR in audio callback: {e}")
    
    def start_recording(self) -> bool:
        """Inicia gravação com proteção thread-safe."""
        with self._lock:
            if self._is_recording and not self._is_paused:
                return False
                
            try:
                # Reset completo do estado
                self._audio_queue = queue.Queue(maxsize=self.MAX_QUEUE_SIZE)
                self._dropped_frames = 0
                self._segments_count = 0
                self._total_duration = 0.0
                
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
                
                # Flags de controle
                self._is_recording = True
                self._is_paused = False
                self._processor_running = True
                
                # Inicia thread para processar fila ANTES do stream
                self._processor_thread = threading.Thread(
                    target=self._process_audio_queue,
                    daemon=True
                )
                self._processor_thread.start()
                
                # Inicia stream
                self._stream = sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    dtype=self.dtype,
                    callback=self._audio_callback,
                    blocksize=2048
                )
                self._stream.start()
                
                self._start_time = datetime.now()
                self._notify_status("recording_started")
                return True
                
            except Exception as e:
                print(f"Failed to start recording: {e}")
                self._cleanup()
                return False
    
    def _process_audio_queue(self):
        """Processa fila de áudio e salva em disco."""
        while self._processor_running:
            try:
                # Timeout curto para responder rápido ao stop
                segment = self._audio_queue.get(timeout=0.1)
                
                # Salva no arquivo temporário
                if self._wave_writer and not self._wave_writer.closed:
                    self._wave_writer.write(segment.data.flatten())
                    self._segments_count += 1
                    self._total_duration += segment.duration
                    
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error processing audio: {e}")
        
        # Esvazia fila restante antes de sair
        while not self._audio_queue.empty():
            try:
                segment = self._audio_queue.get_nowait()
                if self._wave_writer and not self._wave_writer.closed:
                    self._wave_writer.write(segment.data.flatten())
            except:
                break
    
    def pause_recording(self) -> bool:
        """Pausa gravação mantendo dados."""
        with self._lock:
            if not self._is_recording or self._is_paused:
                return False
                
            self._is_paused = True
            
            # Para o stream mas mantém arquivo aberto
            if self._stream:
                self._stream.stop()
                
            self._notify_status("recording_paused")
            return True
    
    def resume_recording(self) -> bool:
        """Retoma gravação no mesmo arquivo."""
        with self._lock:
            if not self._is_recording or not self._is_paused:
                return False
                
            try:
                self._is_paused = False
                
                # Retoma stream
                if self._stream:
                    self._stream.start()
                
                self._notify_status("recording_resumed")
                return True
                
            except Exception as e:
                print(f"Failed to resume recording: {e}")
                return False
    
    def stop_recording(self) -> Optional[str]:
        """Para gravação e retorna caminho do arquivo."""
        with self._lock:
            if not self._is_recording:
                return None
                
            # Para gravação primeiro
            self._is_recording = False
            self._is_paused = False
            
            # Para stream
            if self._stream:
                try:
                    self._stream.stop()
                    self._stream.close()
                except:
                    pass
                self._stream = None
            
            # Para thread processadora
            self._processor_running = False
            
            # Aguarda thread terminar (máximo 2 segundos)
            if self._processor_thread and self._processor_thread.is_alive():
                self._processor_thread.join(timeout=2.0)
            
            # Fecha arquivo
            temp_path = None
            if self._wave_writer:
                try:
                    self._wave_writer.close()
                    if self._temp_file:
                        temp_path = self._temp_file.name if self._temp_file else None
                except:
                    pass
                self._wave_writer = None
            
            self._temp_file = None
            
            # Log de frames perdidos
            if self._dropped_frames > 0:
                print(f"Total dropped frames: {self._dropped_frames}")
            
            self._notify_status("recording_stopped")
            
            return temp_path
    
    def _cleanup(self):
        """Limpa recursos em caso de erro."""
        self._is_recording = False
        self._is_paused = False
        self._processor_running = False
        
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
        
        # Esvazia fila
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except:
                break
    
    @property
    def is_recording(self) -> bool:
        """Retorna status de gravação thread-safe."""
        with self._lock:
            return self._is_recording and not self._is_paused
    
    @property
    def recording_stats(self) -> dict:
        """Retorna estatísticas da gravação atual."""
        with self._lock:
            if not self._start_time:
                return {
                    "duration": 0,
                    "segments": 0,
                    "status": "idle",
                    "queue_size": 0,
                    "dropped_frames": 0
                }
            
            status = "idle"
            if self._is_recording:
                status = "paused" if self._is_paused else "recording"
                
            duration = (datetime.now() - self._start_time).total_seconds()
            return {
                "duration": duration,
                "segments": self._segments_count,
                "status": status,
                "queue_size": self._audio_queue.qsize(),
                "dropped_frames": self._dropped_frames
            }
            
    def __del__(self):
        """Garante limpeza ao destruir objeto."""
        self._cleanup()