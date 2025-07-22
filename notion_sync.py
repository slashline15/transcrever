from notion_client import Client
from storage import TranscriptionStorage
import os
from datetime import datetime
from openai import OpenAI

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_TRANSCRIPTIONS_DB")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

class NotionSync:
    def __init__(self):
        self.notion = Client(auth=NOTION_TOKEN)
        self.storage = TranscriptionStorage()
        self.openai = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

    def _generate_headline(self, text: str) -> str:
        """Gera um resumo/headline curto para título de página Notion."""
        if not self.openai:
            return text[:60]
        prompt = (
            "Extraia um resumo curto e objetivo deste texto para ser usado como título. "
            "Máximo de 120 caracteres, sem pontuação no final, sem aspas:\n\n"
            f"{text[:1800]}"
        )
        try:
            response = self.openai.chat.completions.create(
                model="gpt-4-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=60
            )
            headline = response.choices[0].message.content.strip().replace('\n', ' ')
            if len(headline) > 120:
                headline = headline[:117] + "..."
            return headline
        except Exception:
            return text[:60]

    def create_transcription_page(self, transcription_id: int):
        """Cria página no Notion para transcrição."""
        t = self.storage.get_transcription(transcription_id)
        if not t:
            return None

        # Texto para campo Transcrição e para título
        main_text = t.enhanced_text or t.raw_text or ""
        headline = self._generate_headline(main_text)

        # Propriedades da página
        properties = {
            "Title": {"title": [{"text": {"content": headline}}]},
            "Transcrição": {"rich_text": [{"text": {"content": main_text[:2000]}}]},
            "Data": {"date": {"start": t.created_at}},
            "Duração": {"number": t.audio_duration},
            "Custo": {"number": t.cost_usd},
            "Modelo": {"select": {"name": t.whisper_model}},
            "Status": {"select": {"name": "Processada"}}
        }

        # Conteúdo (blocos para visualização detalhada)
        children = [
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"text": {"content": "📝 Texto Original"}}]
                }
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"text": {"content": t.raw_text[:2000]}}]
                }
            }
        ]

        # Adiciona versão aprimorada se existir
        if t.enhanced_text:
            children.extend([
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"text": {"content": "✨ Texto Aprimorado"}}]
                    }
                },
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"text": {"content": t.enhanced_text[:2000]}}]
                    }
                }
            ])

        # Cria página
        page = self.notion.pages.create(
            parent={"database_id": NOTION_DATABASE_ID},
            properties=properties,
            children=children
        )

        return page["id"]