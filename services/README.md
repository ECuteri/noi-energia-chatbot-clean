# Modulo Services

Questo modulo contiene servizi logica di business per il sistema chatbot documentale.

## Componenti

### `supabase_client.py`
Client unificato per tutte le operazioni Supabase.

**Caratteristiche:**
- Gestione documenti (elenco, get, ricerca)
- Ricerca similarità vettoriale con embedding OpenAI
- Archiviazione e recupero cronologia chat
- Gestione connessioni e gestione errori

**Metodi Chiave:**
```python
# Operazioni documenti
await supabase_store.list_documents(table_name, metadata_table_name, limit, offset)
await supabase_store.get_document(document_id, table_name, metadata_table_name)

# Ricerca vettoriale
await supabase_store.search_similar(query, table_name, limit)

# Cronologia chat
await supabase_store.save_chat_message(session_id, role, content)
await supabase_store.get_chat_history(session_id, limit)

# Embedding
await supabase_store.embed_text(text)
```

**Configurazione:**
- `SUPABASE_URL`: URL progetto Supabase
- `SUPABASE_API_KEY`: Chiave API Supabase
- `OPENAI_API_KEY`: Per generazione embedding
- `EMBEDDING_MODEL`: Modello da utilizzare (default: text-embedding-3-small)

### `voice_transcription.py`
Servizio trascrizione audio che supporta Gemini e OpenAI Whisper.

**Caratteristiche:**
- Download e validazione audio
- Supporto multi-provider (Gemini, OpenAI)
- Rilevamento formato e conversione
- Gestione errori e logica retry

**Funzioni Chiave:**
```python
# Trascrivi audio da URL
transcription = await transcribe_audio_from_url(audio_url)

# Processa messaggio con allegati
result = await process_message_attachments(attachments, content)
```

**Formati Supportati:**
- OGG/Opus
- MP3
- M4A/MP4
- WAV
- WebM
- FLAC

**Configurazione:**
- `TRANSCRIPTION_PROVIDER`: "gemini" o "openai"
- `GEMINI_API_KEY`: Per trascrizione Gemini
- `OPENAI_API_KEY`: Per trascrizione Whisper

### `chatwoot.py`
Integrazione Chatwoot per invio messaggi a conversazioni.

**Caratteristiche:**
- Invia messaggi testo a conversazioni Chatwoot
- Invia allegati media con didascalie
- Supporto per messaggi privati
- Gestione errori robusta per URL media
- Autenticazione flessibile (token API o token bot)

**Funzioni Chiave:**
```python
# Invia messaggio testo
result = await send_chatwoot_message(
    conversation_id=123,
    contact_identifier="user@example.com",
    text="Ciao dal bot!"
)

# Invia messaggio media
result = await send_chatwoot_message(
    conversation_id=123,
    contact_identifier="user@example.com",
    media_url="https://example.com/image.jpg",
    caption="Guarda questa immagine"
)

# Invia nota privata
result = await send_chatwoot_message(
    conversation_id=123,
    contact_identifier="user@example.com",
    text="Nota interna",
    private=True
)
```

**Configurazione:**
- `CHATWOOT_BASE_URL`: URL istanza Chatwoot
- `CHATWOOT_ACCOUNT_ID`: Identificatore account
- `CHATWOOT_API_ACCESS_TOKEN`: Token accesso API per invio messaggi

**Autenticazione Webhook Per-Agente:**
Ogni agente ha credenziali separate per sicurezza webhook:
- Noi CER:
  - `CHATWOOT_NOI_CER_INBOX_ID`: Identificatore inbox
  - `CHATWOOT_NOI_CER_BOT_TOKEN`: Token bot per auth webhook
  - `CHATWOOT_NOI_CER_WEBHOOK_SECRET`: Secret HMAC per auth webhook
- Noi Energia:
  - `CHATWOOT_NOI_ENERGIA_INBOX_ID`: Identificatore inbox
  - `CHATWOOT_NOI_ENERGIA_BOT_TOKEN`: Token bot per auth webhook
  - `CHATWOOT_NOI_ENERGIA_WEBHOOK_SECRET`: Secret HMAC per auth webhook

**Gestione Errori:**
- Restituisce dict stato con "success", "error", o "config_error"
- Valida URL media prima dell'invio
- Gestisce fallimenti connessione gracefully
- Timeout per download media (10s totali, 5s connect)

## Esempi Utilizzo

### Ricerca Documenti
```python
from services.supabase_client import supabase_store

# Elenca documenti
docs = await supabase_store.list_documents(
    table_name="noi_cer_documents",
    metadata_table_name="noi_cer_documents_metadata",
    limit=10
)

# Ricerca vettoriale
results = await supabase_store.search_similar(
    query="energia rinnovabile",
    table_name="noi_cer_documents",
    limit=5
)
```

### Trascrizione Vocale
```python
from services.voice_transcription import transcribe_audio_from_url

transcription = await transcribe_audio_from_url(
    "https://example.com/audio.ogg"
)
```

### Integrazione Chatwoot
```python
from services.chatwoot import send_chatwoot_message

result = await send_chatwoot_message(
    conversation_id=12345,
    contact_identifier="user@example.com",
    text="Ciao! Come posso aiutarti oggi?"
)

if result.get("status") == "success":
    print("Messaggio inviato con successo")
```

## Gestione Errori

Tutti i servizi implementano gestione errori completa:
- Degradazione graceful su fallimenti
- Logging errori dettagliato
- Messaggi errore user-friendly
- Retry automatici dove appropriato

## Performance

### Client Supabase
- Connection pooling gestito da Supabase
- Ricerca vettoriale efficiente con indice IVFFlat
- Supporto paginazione per grandi set risultati
- Caching di embedding

### Trascrizione Vocale
- Timeout 30 secondi per download
- Limite dimensione file 25MB
- Processing asincrono per operazioni non-blocking
- Supporto fallback provider

## Testing

```python
# Test connessione Supabase
from services.supabase_client import supabase_store
docs = await supabase_store.list_documents(
    "noi_cer_documents",
    "noi_cer_documents_metadata",
    limit=1
)

# Test trascrizione vocale
from services.voice_transcription import transcribe_audio_from_url
text = await transcribe_audio_from_url("https://example.com/test.ogg")
```
