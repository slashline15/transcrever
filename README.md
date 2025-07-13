# Transcritor de Áudio v2 - Instalação Rápida

## O que mudou na v2

### ✅ Problemas Resolvidos:
1. **Histórico de Transcrições** - Nunca mais perca uma transcrição!
   - SQLite local salva todas as transcrições
   - Atalho `Ctrl + Shift + H` para acessar histórico
   - Recopiar transcrições antigas com 1 clique

2. **Thread-Safety** - Sem travamentos ou corrupção
   - Fila protegida para áudio
   - Gravação em arquivo temporário (não mais tudo em RAM)

3. **Custos e Progresso** - Transparência total
   - Mostra custo de cada transcrição
   - Barra de progresso durante processamento
   - Estatísticas totais de uso

## Estrutura dos Arquivos

```
audio-recorder-v2/
├── audio_core.py       # Módulo de captura (Sprint 0)
├── storage.py          # Persistência SQLite (Sprint 1)  
├── main_v2.py          # Interface refatorada (Sprint 2)
├── requirements.txt    # Dependências
├── .env                # Sua API key
└── build.py            # Script para gerar .exe
```

## Instalação

1. **Instale as dependências:**
```bash
pip install -r requirements.txt
```

2. **Configure sua API Key no `.env`:**
```
OPENAI_API_KEY=sua_chave_aqui
```

3. **Execute direto ou gere o .exe:**
```bash
# Testar primeiro
python main_v2.py

# Gerar executável
python build.py
```

## Uso

### Atalhos:
- `Ctrl + Shift + R` - Gravar/Pausar
- `Ctrl + Shift + S` - Finalizar e transcrever
- `Ctrl + Shift + H` - Abrir histórico

### Recursos Novos:
- **Histórico**: Acesse até 20 transcrições anteriores
- **Custos**: Veja quanto cada transcrição custou
- **Progresso**: Acompanhe o processamento em tempo real
- **Logs destacados**: Info 🟢 Avisos 🟡 Erros 🔴

### Dados Salvos:
- Banco SQLite em: `~/.audio_recorder/transcriptions.db`
- Exportar histórico: Em breve no menu

## Próximos Passos (Sprints 3-6)

- [ ] Sprint 3: Interface minimalista na bandeja
- [ ] Sprint 4: Templates de tom (Cortella mode!)
- [ ] Sprint 5: Integração Notion/Telegram
- [ ] Sprint 6: Whisper local com GPU

## Problemas Conhecidos

- Em gravações muito longas (>30min), o Whisper pode demorar
- Custos são estimados (tokens aproximados)

---

**Importante**: Esta é uma versão funcional mas ainda em desenvolvimento. 
Reporte bugs e sugestões!