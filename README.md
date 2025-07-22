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

## Roadmap dos Sprints e Próximas Evoluções

### Sprint 1: Refatoração e Testes — Base Sólida
**Objetivo**: Garantir que todo o core seja estável, modular, fácil de manter e testável.
**Benefícios**: Menor incidência de bugs, onboarding facilitado, confidência para futuras inovações.
**Principais etapas**:
- Refatoração dos principais módulos para clareza, atomicidade e responsabilidade única.
- Cobertura de testes abrangente (unitários/integrados) e casos de uso críticos.
- Auditoria nos fluxos de erro e logs automatizados para rastreabilidade.
- Garantia de compatibilidade cross-platform (Windows, Linux, future Mac).
---
### Sprint 2: Whisper Local + VAD (Voice Activity Detection)
**Objetivo**: Reduzir significativamente custos substituindo chamadas à API por processamento local com Whisper otimizado/VAD.
**Benefícios**: Operação mais barata e privativa, viabilizando uso de grandes volumes/falar por longos períodos.
**Principais etapas**:
- Integração do Whisper local (GPU/CPU fallback).
- Voz ativa (VAD): transcrição automática só quando houver fala.
- Benchmarks de performance, configuração ajustável e fallback seguro.
---
### Sprint 3: UX Avançada — Importação, Buscas e Gráficos
**Objetivo**: Proporcionar experiência de usuário de excelência, otimizando o fluxo de informação.
**Benefícios**: Facilidade para localizar, visualizar e gerenciar múltiplas transcrições.
**Principais etapas**:
- Sistema de importação de arquivos externos (áudio/texto).
- Busca rápida por termo, data, ou tags.
- Visualização gráfica das estatísticas de uso e perfil de transcrições.
---
### Sprint 4: Modos Inteligentes e Etiquetas
**Objetivo**: Oferecer valor avançado ao usuário com personalização e organização inteligente do workflow.
**Benefícios**: Transcrição customizada ao contexto (ex: acadêmico, resumo, motivacional) e fácil categorização por etiquetas.
**Principais etapas**:
- Templates de estilo (inclusive “modo Cortella”, sumarização, bullet point, etc).
- Sistema de criação/gestão de tags e filtros combináveis.
- Interface para aplicação dinâmica de configurações no momento da transcrição.
---
### Sprint 5: Integrações e Automações Escaláveis (API, Telegram, CI/CD)
**Objetivo**: Tornar a solução verdadeiramente escalável e automatizável.
**Benefícios**: Fluxos mais rápidos, integração com canais de entrada e API, deploy contínuo, workflows parametrizáveis.
**Principais etapas**:
- API RESTful para consumo externo e integrações via webhooks.
- Integração refinada com Telegram (envio, busca, histórico, comandos on demand).
- Setup automatizado de pipelines de CI/CD, deploy multiambiente.
- Documentação detalhada e exemplos de automação.

---

## Problemas Conhecidos

- Em gravações muito longas (>30min), o Whisper pode demorar
- Custos são estimados (tokens aproximados)

---

**Importante**: Esta é uma versão funcional mas ainda em desenvolvimento. 
Reporte bugs e sugestões!