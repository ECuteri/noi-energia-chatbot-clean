# Modulo Database

Questo modulo gestisce tutte le operazioni database per il sistema chatbot Noi Energia utilizzando Supabase come provider database primario.

## Architettura

Il sistema utilizza **Supabase** (PostgreSQL con estensione pgvector) per:
- **Cronologia Chat**: Archiviazione conversazioni per entrambi i chatbot
- **Archiviazione Documenti**: Contenuto documenti e metadati
- **Embedding Vettoriali**: Ricerca semantica con embedding OpenAI

### Modello Dati

**Pattern Due Tabelle per Chatbot:**

1. **Tabella Metadati** (`*_documents_metadata`)
   - Archivia una riga per documento sorgente (file Google Drive)
   - Chiave primaria è l'ID file esterno (ID Google Drive)
   - Contiene titolo, data creazione e altri metadati livello file

2. **Tabella Documenti** (`*_documents`)
   - Archivia molteplici chunk per documento sorgente
   - Ogni chunk ha propria chiave primaria UUID
   - Contiene contenuto testo ed embedding vettoriali per ricerca semantica
   - Linka a file sorgente tramite campo JSONB `metadata->>'file_id'`
   - Gestito da automazione vector store n8n

**Perché Tabelle Separate?**
- Tabella metadati traccia file sorgente (una riga per file)
- Tabella documenti archivia contenuto chunked per RAG (molte righe per file)
- Nessun vincolo foreign key permette a vector store di gestire chunk indipendentemente
- Link mantenuto tramite campo JSONB metadati per flessibilità

**ID Auto-Generati:**
- Tabelle documenti usano trigger per auto-generare UUID quando `id` è NULL
- Gestisce n8n vector store che passa esplicitamente valori NULL
- Trigger si attivano prima di INSERT, convertendo NULL in gen_random_uuid()::text
- Assicura compatibilità con tool automazione esterni

## Componenti

### `init_supabase.py`
Gestisce inizializzazione schema Supabase e verifica tabelle.

**Funzioni:**
- `initialize_supabase_schema()`: Crea automaticamente tabelle, indici e abilita estensione pgvector
- `verify_supabase_tables()`: Controlla esistenza di tutte le tabelle richieste
- `print_setup_instructions()`: Mostra istruzioni setup SQL manuale (fallback)

### Tabelle Richieste

#### 1. chat_history
Archivia messaggi conversazione per entrambi i chatbot.
```sql
CREATE TABLE chat_history (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### 2. noi_cer_documents_metadata
Archivia metadati per documenti sorgente Noi CER (una riga per file).
```sql
CREATE TABLE noi_cer_documents_metadata (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```
**Nota**: `id` è l'ID file Google Drive o identificatore documento esterno.

#### 3. noi_cer_documents
Archivia chunk documenti Noi CER con embedding vettoriali (multipli chunk per file).
```sql
CREATE TABLE noi_cer_documents (
    id TEXT PRIMARY KEY,
    metadata JSONB DEFAULT '{}',
    embedding VECTOR(1536),
    content TEXT
);

-- Trigger auto-genera ID se fornito NULL
CREATE TRIGGER noi_cer_documents_id_trigger
    BEFORE INSERT ON noi_cer_documents
    FOR EACH ROW
    EXECUTE FUNCTION generate_noi_cer_doc_id();
```
**Nota**:
- `id` è UUID auto-generato (tramite trigger quando NULL)
- Trigger gestisce n8n vector store che passa esplicitamente NULL
- `metadata->>'file_id'` contiene l'ID file sorgente che linka alla tabella metadati
- Gestito da automazione vector store n8n

#### 4. noi_energia_documents_metadata
Archivia metadati per documenti sorgente Noi Energia (una riga per file).
```sql
CREATE TABLE noi_energia_documents_metadata (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```
**Nota**: `id` è l'ID file Google Drive o identificatore documento esterno.

#### 5. noi_energia_documents
Archivia chunk documenti Noi Energia con embedding vettoriali (multipli chunk per file).
```sql
CREATE TABLE noi_energia_documents (
    id TEXT PRIMARY KEY,
    metadata JSONB DEFAULT '{}',
    embedding VECTOR(1536),
    content TEXT
);

-- Trigger auto-genera ID se fornito NULL
CREATE TRIGGER noi_energia_documents_id_trigger
    BEFORE INSERT ON noi_energia_documents
    FOR EACH ROW
    EXECUTE FUNCTION generate_noi_energia_doc_id();
```
**Nota**:
- `id` è UUID auto-generato (tramite trigger quando NULL)
- Trigger gestisce n8n vector store che passa esplicitamente NULL
- `metadata->>'file_id'` contiene l'ID file sorgente che linka alla tabella metadati
- Gestito da automazione vector store n8n

## Istruzioni Setup

1. **Crea Progetto Supabase**
   - Vai su [supabase.com](https://supabase.com)
   - Crea un nuovo progetto
   - Nota il tuo URL progetto e chiave API

2. **Configura Variabili Ambiente**
   ```bash
   SUPABASE_URL=https://il-tuo-progetto.supabase.co
   SUPABASE_API_KEY=la-tua-chiave-api-supabase
   ```

3. **Creazione Automatica Tabelle**
   Le tabelle sono create automaticamente al primo avvio quando chiami `initialize_supabase_schema()`.
   L'inizializzazione eseguirà:
   - Abilita estensione pgvector (se permessi lo consentono)
   - Crea tutte le tabelle richieste se non esistono
   - Crea indici per performance ottimali
   - Verifica che tutte le tabelle siano state create con successo

4. **Setup Manuale (Opzionale)**
   Se la creazione automatica fallisce per problemi permessi, puoi eseguire manualmente l'SQL:
   ```python
   from database.init_supabase import print_setup_instructions
   print_setup_instructions()
   ```

## Utilizzo

### Inizializza Schema
```python
from database.init_supabase import initialize_supabase_schema

await initialize_supabase_schema()
```

### Verifica Tabelle
```python
from database.init_supabase import verify_supabase_tables

status = await verify_supabase_tables()
print(status)
```

## Client Supabase

Il modulo `services/supabase_client.py` fornisce un'interfaccia unificata per tutte le operazioni database:

- **Operazioni Documenti**: list_documents, get_document
- **Ricerca Vettoriale**: search_similar (con embedding OpenAI)
- **Cronologia Chat**: save_chat_message, get_chat_history

## Considerazioni Performance

- **Indici**: Creati su colonne frequentemente interrogate
- **Ricerca Vettoriale**: Usa indice IVFFlat per ricerca similarità efficiente
- **Paginazione**: Supportata per grandi set risultati
- **Connection Pooling**: Gestito da Supabase

## Risoluzione Problemi

### Tabelle Non Esistono
Esegui lo script di inizializzazione o esegui manualmente l'SQL da `init_supabase.py`.

### pgvector Non Disponibile
Assicurati che l'estensione pgvector sia abilitata nel tuo progetto Supabase.

### Problemi Connessione
Verifica il tuo SUPABASE_URL e SUPABASE_API_KEY nelle variabili ambiente.
