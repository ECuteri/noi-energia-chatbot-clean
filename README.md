# Sistema di Chatbot Documentale Noi Energia

Sistema di chatbot documentale basato su AI pronto per la produzione, che presenta due chatbot specializzati per il recupero e la ricerca semantica di documenti utilizzando l'archiviazione vettoriale Supabase e gli embedding OpenAI.

## Panoramica

Questo sistema fornisce accesso intelligente ai documenti attraverso query in linguaggio naturale, alimentato da tecnologia LLM avanzata e ricerca semantica basata su vettori. Il sistema ospita due chatbot specializzati:

- **Chatbot Noi CER**: Specializzato per la documentazione Noi CER
- **Chatbot Noi Energia**: Specializzato per la documentazione Noi Energia

## Caratteristiche

### Capacità Core
- **Ricerca Semantica**: Recupero documenti basato su vettori utilizzando embedding OpenAI
- **Gestione Documenti**: Elenco, ricerca e recupero contenuti documenti
- **Trascrizione Vocale**: Supporto per messaggi audio tramite Gemini o OpenAI Whisper
- **Cronologia Chat**: Archiviazione persistente delle conversazioni in Supabase
- **API RESTful**: Endpoint HTTP semplici per testing e integrazione

### Caratteristiche Tecniche
- **Architettura Asincrona**: Costruito con Quart per operazioni asincrone ad alte prestazioni
- **Integrazione Supabase**: PostgreSQL con pgvector per ricerca vettoriale efficiente
- **Agenti LangGraph**: Orchestrazione intelligente di agenti con capacità di chiamata tool
- **Inferenza Groq**: Inferenza LLM veloce con modello openai/gpt-oss-120b
- **Pronto per la Produzione**: Gestione errori completa e logging

## Architettura

```
┌─────────────────────┐
│   API HTTP          │
│   (Quart)           │
└──────────┬──────────┘
           │
           ├─── Chatbot Noi CER
           │    └── Tool: list, get, search
           │
           └─── Chatbot Noi Energia
                └── Tool: list, get, search

┌─────────────────────────────────────┐
│  Supabase (PostgreSQL + pgvector)  │
├─────────────────────────────────────┤
│  • noi_cer_documents                │
│  • noi_cer_documents_metadata       │
│  • noi_energia_documents            │
│  • noi_energia_documents_metadata   │
│  • chat_history                     │
└─────────────────────────────────────┘
```

## Struttura del Progetto

```
noienergia-chatbot/
├── app.py
├── config.py
├── requirements.txt
├── .env
│
├── chatbots/
│   ├── common/
│   │   ├── schemas.py
│   │   ├── agent_factory.py
│   │   └── tools/
│   │       ├── list_documents.py
│   │       ├── get_file_contents.py
│   │       └── vector_search.py
│   ├── noi_cer_chatbot/
│   │   └── agent.py
│   └── noi_energia_chatbot/
│       └── agent.py
│
├── services/
│   ├── supabase_client.py
│   └── voice_transcription.py
│
├── routes/
│   ├── local_test.py
│   └── chat_history_routes.py
│
├── database/
│   ├── init_supabase.py
│   └── README.md
│
└── prompts/
    └── README.md
```

## Installazione

### Prerequisiti
- Python 3.13+
- Account Supabase
- **Chiave API OpenAI** (richiesta per generazione embedding vettoriali e trascrizione opzionale)
- **Chiave API Groq** (richiesta per inferenza LLM)
- **Chiave API Gemini** (richiesta per trascrizione vocale con Gemini)

### Passi di Setup

1. **Clona il repository**
   ```bash
   git clone <repository-url>
   cd noienergia-chatbot
   ```

2. **Crea ambiente virtuale**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Su Windows: venv\Scripts\activate
   ```

3. **Installa dipendenze**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configura variabili d'ambiente**
   ```bash
   # Esegui script deploy per generare template .env
   ./deploy.sh
   # Oppure crea manualmente .env dal template in deploy.sh
   # Modifica .env con le tue credenziali
   ```

5. **Setup database Supabase**
   ```python
   from database.init_supabase import print_setup_instructions
   print_setup_instructions()
   # Esegui l'SQL nell'editor SQL di Supabase
   ```

6. **Avvia l'applicazione**
   ```bash
   python app.py
   ```

## Configurazione

### Variabili d'Ambiente Richieste

```bash
OPENAI_API_KEY=sk-la-tua-chiave-openai
GROQ_API_KEY=gsk-la-tua-chiave-groq
GEMINI_API_KEY=la-tua-chiave-gemini

SUPABASE_URL=https://il-tuo-progetto.supabase.co
SUPABASE_API_KEY=la-tua-api-key-supabase

TRANSCRIPTION_PROVIDER=gemini

PORT=5001
LOG_LEVEL=INFO
```

### Opzioni di Configurazione Complete

Tutta la configurazione è gestita attraverso variabili d'ambiente. Crea un file `.env` nella root del progetto:

```bash
OPENAI_API_KEY=sk-la-tua-chiave-openai
GROQ_API_KEY=gsk-la-tua-chiave-groq
GEMINI_API_KEY=la-tua-chiave-gemini

SUPABASE_URL=https://il-tuo-progetto.supabase.co
SUPABASE_API_KEY=la-tua-api-key-supabase

TRANSCRIPTION_PROVIDER=gemini

PORT=5001
APP_DEBUG=false

LOG_LEVEL=INFO
LOG_TO_FILE=true
LOG_FILE_PATH=app.log
LOG_MAX_SIZE=10485760
LOG_BACKUP_COUNT=5
LOG_USE_JSON_FORMAT=false

CHATBOTS_LOG_LEVEL=WARNING
DATABASE_LOG_LEVEL=WARNING
HTTPX_LOG_LEVEL=WARNING
LANGCHAIN_LOG_LEVEL=WARNING
OPENAI_LOG_LEVEL=WARNING

DEFAULT_COLLECTION=default
MAX_SEARCH_RESULTS=10
EMBEDDING_MODEL=text-embedding-3-small
SIMILARITY_THRESHOLD=0.3

CHATWOOT_BASE_URL=https://la-tua-istanza-chatwoot.com
CHATWOOT_ACCOUNT_ID=il_tuo_account_id
CHATWOOT_API_ACCESS_TOKEN=il_tuo_api_access_token
CHATWOOT_NOI_CER_INBOX_ID=il_tuo_inbox_id_cer
CHATWOOT_NOI_CER_BOT_TOKEN=il_tuo_bot_token_cer
CHATWOOT_NOI_CER_WEBHOOK_SECRET=il_tuo_webhook_secret_cer
CHATWOOT_NOI_ENERGIA_INBOX_ID=il_tuo_inbox_id_energia
CHATWOOT_NOI_ENERGIA_BOT_TOKEN=il_tuo_bot_token_energia
CHATWOOT_NOI_ENERGIA_WEBHOOK_SECRET=il_tuo_webhook_secret_energia
```

Per il deployment in produzione, usa:
```bash
LOG_LEVEL=WARNING
LOG_USE_JSON_FORMAT=true
LOG_FILE_PATH=/var/log/noienergia-chatbot/app.log
```

### Spiegazione Chiavi API

**OPENAI_API_KEY** 🔑
- **Utilizzo**: Generazione di embedding vettoriali per ricerca semantica dei documenti
- **Modello**: `text-embedding-3-small` (configurabile)
- **Quando serve**: Sempre richiesta - necessaria per la funzionalità core di ricerca documenti

**GROQ_API_KEY** 🤖
- **Utilizzo**: Inferenza del modello di linguaggio per generare risposte dei chatbot
- **Modello**: `openai/gpt-oss-120b` (ottimizzato per velocità)
- **Quando serve**: Sempre richiesta - necessaria per le risposte dei chatbot

**GEMINI_API_KEY** 🎙️
- **Utilizzo**: Trascrizione di messaggi vocali in testo (provider predefinito)
- **Alternativa**: Puoi usare `TRANSCRIPTION_PROVIDER=openai` per usare OpenAI Whisper
- **Quando serve**: Richiesta se vuoi supportare trascrizione vocale, altrimenti opzionale

## Endpoint API

### Chat con Chatbot
```http
POST /local-chat
Content-Type: application/json

{
  "user_id": "user123",
  "message": "Quali documenti hai sull'efficienza energetica?",
  "chatbot": "noi_cer"
}
```

**Risposta:**
```json
{
  "status": "success",
  "user_id": "user123",
  "session_id": "user123",
  "chatbot": "noi_cer",
  "response": "Ho trovato diversi documenti sull'efficienza energetica...",
  "messages_returned": 3
}
```

### Ottieni Cronologia Chat
```http
GET /chat-history/<session_id>?limit=50
```

**Risposta:**
```json
{
  "session_id": "user123",
  "messages": [
    {"role": "user", "content": "Ciao"},
    {"role": "assistant", "content": "Ciao! Come posso aiutarti?"}
  ],
  "total_messages": 2
}
```

### Reset Sessione Chat
```http
POST /local-chat/reset
Content-Type: application/json

{
  "user_id": "user123"
}
```

## Tool Chatbot

Ogni chatbot ha accesso a tre tool specializzati:

### 1. list_documents
Sfoglia documenti disponibili con paginazione.
```python
list_documents(limit=50, offset=0)
```

### 2. get_file_contents
Recupera contenuto completo documento tramite ID.
```python
get_file_contents(document_id="uuid-here")
```

### 3. vector_search
Ricerca semantica utilizzando embedding OpenAI.
```python
vector_search(query="energia rinnovabile", limit=10)
```

## Schema Database

### chat_history
Archivia messaggi conversazione.
- `id`: Chiave primaria seriale
- `session_id`: Identificatore sessione utente
- `role`: Ruolo messaggio (user/assistant)
- `content`: Contenuto messaggio
- `created_at`: Timestamp

### Tabelle Documenti
Ogni chatbot ha due tabelle:
- `{chatbot}_documents`: Contenuto ed embedding
- `{chatbot}_documents_metadata`: Metadati e relazioni

## Sviluppo

### Esecuzione Test
```bash
curl -X POST http://localhost:5001/local-chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "message": "Elenca documenti disponibili",
    "chatbot": "noi_cer"
  }'
```

### Logging
Il sistema ora include logging completo con molteplici formati di output e controllo granulare:

```bash
LOG_LEVEL=INFO
LOG_TO_FILE=true
LOG_USE_JSON_FORMAT=false

CHATBOTS_LOG_LEVEL=WARNING
DATABASE_LOG_LEVEL=WARNING
HTTPX_LOG_LEVEL=WARNING
LANGCHAIN_LOG_LEVEL=WARNING
OPENAI_LOG_LEVEL=WARNING
```

### Caratteristiche Logging Avanzate

**Logging Strutturato**: Imposta `LOG_USE_JSON_FORMAT=true` per log formattati JSON più facili da analizzare.

**Monitoraggio Performance**: Le richieste webhook ora includono informazioni temporali per autorizzazione, processamento e tempi di risposta.

**Contesto Errori Dettagliato**: Tutti gli errori includono ID richiesta, informazioni temporali e stack trace completi per debugging semplificato.

**Rotazione File**: Rotazione automatica log con limiti dimensione configurabili e conteggio backup.

### Qualità del Codice

Questo progetto utilizza hook [pre-commit](https://pre-commit.com/) per mantenere standard di qualità del codice. Pre-commit esegue automaticamente formattazione codice, linting e altri controlli qualità prima di ogni commit.

#### Setup
```bash
pre-commit install

pre-commit run --all-files

pre-commit run
```

#### Tool Pre-commit
- **black**: Formattazione codice (lunghezza linea 88 caratteri)
- **isort**: Ordinamento import (compatibile con black)
- **flake8**: Linting con regole rilassate per sviluppo
- **Controlli Base**: Spazi finali, fix fine file, validazione sintassi

Gli hook assicurano stile codice consistente e catturano problemi comuni prima che raggiungano il repository.

### Aggiungere Nuovi Documenti
I documenti dovrebbero essere aggiunti direttamente a Supabase:
1. Inserisci contenuto documento in `{chatbot}_documents`
2. Inserisci metadati in `{chatbot}_documents_metadata`
3. Genera embedding utilizzando OpenAI
4. Archivia embedding nella colonna `embedding`

## Trascrizione Vocale

Il sistema supporta trascrizione messaggi audio utilizzando Gemini o OpenAI Whisper.

### Formati Supportati
- OGG/Opus
- MP3
- M4A/MP4
- WAV
- WebM
- FLAC

### Utilizzo
Includi allegati nel tuo messaggio:
```python
{
  "message": "Di cosa si tratta?",
  "attachments": [
    {
      "file_type": "audio",
      "url": "https://example.com/audio.ogg"
    }
  ]
}
```

## Deployment in Produzione

Per istruzioni dettagliate di deployment su Digital Ocean con integrazione Chatwoot, vedi **[DEPLOYMENT.md](DEPLOYMENT.md)**.

### Avvio Rapido con Docker

```bash
./deploy.sh

docker-compose up -d
```

### Caratteristiche Deployment
- Containerizzazione Docker con health check
- Integrazione Nginx per routing webhook
- Validazione automatica ambiente
- Deployment e gestione con un comando

### Setup Ambiente
- Usa istanza Supabase di produzione
- Abilita connection pooling
- Configura livelli logging appropriati
- Setup monitoraggio e alert

### Ottimizzazione Performance
- Abilita indice vettoriale in Supabase (IVFFlat)
- Usa connection pooling
- Cache documenti frequentemente accessiti
- Monitora costi generazione embedding

## Risoluzione Problemi

### Problemi Comuni

**Chatbot non inizializzato**
- Verifica che GROQ_API_KEY sia impostata correttamente
- Controlla log applicazione per errori di avvio

**Ricerca vettoriale non restituisce risultati**
- Assicurati che l'estensione pgvector sia abilitata in Supabase
- Verifica che gli embedding siano generati per i documenti
- Controlla soglia similarità in `supabase_client.py`

**Trascrizione vocale fallisce**
- Verifica GEMINI_API_KEY o OPENAI_API_KEY
- Controlla che il formato file audio sia supportato
- Assicurati che la dimensione file sia sotto 25MB

### Log e Debugging
```bash
tail -f app.log

tail -f app.log | grep "req_"

LOG_USE_JSON_FORMAT=true LOG_LEVEL=DEBUG python app.py

LOG_LEVEL=DEBUG python app.py 2>&1 | grep -E "(cw:|req_|ERROR|WARN)"

tail -f app.log | grep -E "Total time:|Auth time:|Agent time:"
```

## Sicurezza

- **Chiavi API**: Mai committare chiavi API nel controllo versione
- **Variabili Ambiente**: Usa `.env` per configurazione sensibile
- **Supabase**: Abilita policy Row Level Security (RLS)
- **Validazione Input**: Tutti gli input sono validati e sanitizzati
- **Rate Limiting**: Implementa rate limiting per uso produzione

## Contributi

### Stile Codice
- Segui linee guida PEP 8
- Massimo 300 linee per file
- Usa snake_case per funzioni e variabili
- Docstring complete per tutte le funzioni

### Testing
- Testa tutti gli endpoint prima del commit
- Verifica accuratezza risposte chatbot
- Controlla gestione errori per edge case

## Licenza

Proprietaria - Tutti i diritti riservati

## Supporto

Per problemi e domande:
- Controlla documentazione nei README componenti
- Rivedi sezione risoluzione problemi
- Esamina log applicazione
