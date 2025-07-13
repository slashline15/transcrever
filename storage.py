"""
Módulo de persistência para histórico de transcrições.
Sprint 1: SQLite + clipboard history
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass, asdict
import pyperclip
from pathlib import Path

@dataclass
class Transcription:
    """Representa uma transcrição completa."""
    id: Optional[int] = None
    created_at: Optional[str] = None
    raw_text: str = ""
    enhanced_text: Optional[str] = None
    audio_duration: float = 0.0
    whisper_model: str = "whisper-1"
    gpt_model: Optional[str] = None
    tokens_used: int = 0
    cost_usd: float = 0.0
    metadata: Optional[Dict] = None
    
    def to_clipboard_text(self) -> str:
        """Retorna texto para copiar ao clipboard."""
        return self.enhanced_text or self.raw_text

class TranscriptionStorage:
    """Gerenciador de persistência de transcrições."""
    
    # Preços por 1000 tokens (atualizar conforme necessário)
    PRICING = {
        "whisper-1": 0.006,  # por minuto de áudio
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
        "gpt-4": {"input": 0.03, "output": 0.06}
    }
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            # Cria diretório de dados do app
            app_dir = Path.home() / ".audio_recorder"
            app_dir.mkdir(exist_ok=True)
            db_path = str(app_dir / "transcriptions.db")
            
        self.db_path = db_path
        self._init_db()
        
    def _init_db(self):
        """Inicializa banco de dados."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS transcriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    raw_text TEXT NOT NULL,
                    enhanced_text TEXT,
                    audio_duration REAL DEFAULT 0,
                    whisper_model TEXT DEFAULT 'whisper-1',
                    gpt_model TEXT,
                    tokens_used INTEGER DEFAULT 0,
                    cost_usd REAL DEFAULT 0,
                    metadata TEXT
                )
            """)
            
            # Índices para busca rápida
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at 
                ON transcriptions(created_at DESC)
            """)
            
            # Tabela de clipboard history
            conn.execute("""
                CREATE TABLE IF NOT EXISTS clipboard_history (
                    id INTEGER PRIMARY KEY,
                    transcription_id INTEGER,
                    copied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (transcription_id) REFERENCES transcriptions(id)
                )
            """)
            
            conn.commit()
    
    def calculate_cost(self, 
                      audio_duration: float,
                      whisper_model: str,
                      gpt_model: Optional[str] = None,
                      input_tokens: int = 0,
                      output_tokens: int = 0) -> Tuple[float, int]:
        """Calcula custo estimado da transcrição."""
        total_cost = 0.0
        total_tokens = input_tokens + output_tokens
        
        # Custo do Whisper (por minuto)
        if whisper_model in self.PRICING:
            minutes = audio_duration / 60.0
            total_cost += self.PRICING[whisper_model] * minutes
        
        # Custo do GPT (se usado)
        if gpt_model and gpt_model in self.PRICING:
            prices = self.PRICING[gpt_model]
            if isinstance(prices, dict):
                total_cost += (input_tokens / 1000) * prices["input"]
                total_cost += (output_tokens / 1000) * prices["output"]
        
        return round(total_cost, 4), total_tokens
    
    def save_transcription(self, transcription: Transcription) -> int:
        """Salva transcrição e retorna ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Calcula custo se não fornecido
            if transcription.cost_usd == 0:
                cost, tokens = self.calculate_cost(
                    transcription.audio_duration,
                    transcription.whisper_model,
                    transcription.gpt_model,
                    transcription.tokens_used // 2,  # Estimativa
                    transcription.tokens_used // 2
                )
                transcription.cost_usd = cost
            
            # Serializa metadata
            metadata_json = json.dumps(transcription.metadata) if transcription.metadata else None
            
            cursor.execute("""
                INSERT INTO transcriptions 
                (raw_text, enhanced_text, audio_duration, whisper_model, 
                 gpt_model, tokens_used, cost_usd, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                transcription.raw_text,
                transcription.enhanced_text,
                transcription.audio_duration,
                transcription.whisper_model,
                transcription.gpt_model,
                transcription.tokens_used,
                transcription.cost_usd,
                metadata_json
            ))
            
            transcription_id = cursor.lastrowid
            
            # Adiciona ao histórico do clipboard
            self._add_to_clipboard_history(cursor, transcription_id)
            
            conn.commit()
            return transcription_id
    
    def _add_to_clipboard_history(self, cursor, transcription_id: int):
        """Adiciona ao histórico do clipboard."""
        cursor.execute("""
            INSERT INTO clipboard_history (transcription_id)
            VALUES (?)
        """, (transcription_id,))
        
        # Mantém apenas últimos 20 no histórico
        cursor.execute("""
            DELETE FROM clipboard_history
            WHERE id NOT IN (
                SELECT id FROM clipboard_history
                ORDER BY copied_at DESC
                LIMIT 20
            )
        """)
    
    def get_transcription(self, transcription_id: int) -> Optional[Transcription]:
        """Recupera transcrição por ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            row = cursor.execute("""
                SELECT * FROM transcriptions WHERE id = ?
            """, (transcription_id,)).fetchone()
            
            if row:
                return self._row_to_transcription(row)
            return None
    
    def get_recent_transcriptions(self, limit: int = 10) -> List[Transcription]:
        """Recupera transcrições recentes."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            rows = cursor.execute("""
                SELECT * FROM transcriptions
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,)).fetchall()
            
            return [self._row_to_transcription(row) for row in rows]
    
    def get_clipboard_history(self, limit: int = 10) -> List[Tuple[Transcription, str]]:
        """Recupera histórico do clipboard com timestamps."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            rows = cursor.execute("""
                SELECT t.*, ch.copied_at
                FROM clipboard_history ch
                JOIN transcriptions t ON ch.transcription_id = t.id
                ORDER BY ch.copied_at DESC
                LIMIT ?
            """, (limit,)).fetchall()
            
            results = []
            for row in rows:
                transcription = self._row_to_transcription(row)
                copied_at = row['copied_at']
                results.append((transcription, copied_at))
                
            return results
    
    def copy_to_clipboard(self, transcription_id: int) -> bool:
        """Copia transcrição para clipboard e atualiza histórico."""
        transcription = self.get_transcription(transcription_id)
        if transcription:
            text = transcription.to_clipboard_text()
            pyperclip.copy(text)
            
            # Atualiza histórico
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                self._add_to_clipboard_history(cursor, transcription_id)
                conn.commit()
                
            return True
        return False
    
    def get_statistics(self) -> Dict:
        """Retorna estatísticas de uso."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            stats = cursor.execute("""
                SELECT 
                    COUNT(*) as total_transcriptions,
                    SUM(audio_duration) as total_duration,
                    SUM(tokens_used) as total_tokens,
                    SUM(cost_usd) as total_cost,
                    AVG(audio_duration) as avg_duration,
                    AVG(cost_usd) as avg_cost
                FROM transcriptions
            """).fetchone()
            
            return {
                "total_transcriptions": stats[0] or 0,
                "total_duration_seconds": stats[1] or 0,
                "total_duration_minutes": (stats[1] or 0) / 60,
                "total_tokens": stats[2] or 0,
                "total_cost_usd": round(stats[3] or 0, 2),
                "avg_duration_seconds": stats[4] or 0,
                "avg_cost_usd": round(stats[5] or 0, 4)
            }
    
    def _row_to_transcription(self, row: sqlite3.Row) -> Transcription:
        """Converte linha do banco em objeto Transcription."""
        metadata = None
        if row['metadata']:
            metadata = json.loads(row['metadata'])
            
        return Transcription(
            id=row['id'],
            created_at=row['created_at'],
            raw_text=row['raw_text'],
            enhanced_text=row['enhanced_text'],
            audio_duration=row['audio_duration'],
            whisper_model=row['whisper_model'],
            gpt_model=row['gpt_model'],
            tokens_used=row['tokens_used'],
            cost_usd=row['cost_usd'],
            metadata=metadata
        )
    
    def export_to_json(self, output_path: str, limit: Optional[int] = None):
        """Exporta transcrições para JSON."""
        transcriptions = self.get_recent_transcriptions(limit or 1000)
        
        data = {
            "exported_at": datetime.now().isoformat(),
            "statistics": self.get_statistics(),
            "transcriptions": [asdict(t) for t in transcriptions]
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)