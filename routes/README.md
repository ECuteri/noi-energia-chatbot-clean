# Modulo Routes

Endpoint HTTP per il sistema chatbot documentale.

## Route Disponibili

### `local_test.py`
Endpoint per testing e sviluppo locale.

#### POST /local-chat
Chat con uno dei chatbot.

**Richiesta:**
```json
{
  "user_id": "user123",
  "message": "Quali documenti hai?",
  "chatbot": "noi_cer"
}
```

**Parametri:**
- `user_id` (richiesto): Identificatore utente univoco
- `message` (richiesto): Testo messaggio utente
- `chatbot` (opzionale): "noi_cer" o "noi_energia" (default: "noi_cer")

**Risposta:**
```json
{
  "status": "success",
  "user_id": "user123",
  "session_id": "user123",
  "chatbot": "noi_cer",
  "response": "Ecco i documenti disponibili...",
  "messages_returned": 3
}
```

**Risposte Errore:**
- 400: Richiesta non valida (parametri mancanti/non validi)
- 500: Errore server (chatbot non inizializzato, invocazione fallita)

#### POST /local-chat/reset
Reset sessione chat per un utente.

**Richiesta:**
```json
{
  "user_id": "user123"
}
```

**Risposta:**
```json
{
  "status": "success",
  "user_id": "user123",
  "message": "Reset completato"
}
```

### `chat_history_routes.py`
Endpoint per gestione cronologia chat.

#### GET /chat-history/<session_id>
Recupera cronologia chat per una sessione.

**Parametri:**
- `session_id` (path): Identificatore sessione
- `limit` (query, opzionale): Max messaggi da restituire (default: 50)

**Esempio:**
```bash
GET /chat-history/user123?limit=20
```

**Risposta:**
```json
{
  "session_id": "user123",
  "messages": [
    {
      "role": "user",
      "content": "Ciao"
    },
    {
      "role": "assistant",
      "content": "Ciao! Come posso aiutarti?"
    }
  ],
  "total_messages": 2
}
```

**Risposte Errore:**
- 500: Errore database

## Esempi Utilizzo

### Testing Chatbot Noi CER
```bash
curl -X POST http://localhost:5001/local-chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "message": "Elenca tutti i documenti",
    "chatbot": "noi_cer"
  }'
```

### Testing Chatbot Noi Energia
```bash
curl -X POST http://localhost:5001/local-chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "message": "Cerca energia rinnovabile",
    "chatbot": "noi_energia"
  }'
```

### Ottieni Cronologia Chat
```bash
curl http://localhost:5001/chat-history/test_user?limit=10
```

### Reset Sessione
```bash
curl -X POST http://localhost:5001/local-chat/reset \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test_user"}'
```

## Dettagli Implementazione

### Gestione Sessioni
- Session ID è derivato da user_id
- Cronologia chat è automaticamente salvata su Supabase
- Sessioni persistono tra riavvii

### Gestione Errori
- Validazione completa parametri input
- Degradazione graceful su fallimenti servizio
- Logging errori dettagliato
- Messaggi errore user-friendly

### Processing Asincrono
- Tutti gli endpoint utilizzano async/await
- Operazioni I/O non-blocking
- Utilizzo efficiente risorse

## Aggiungere Nuove Route

1. Crea nuovo blueprint:
```python
from quart import Blueprint

my_bp = Blueprint('my_blueprint', __name__)

@my_bp.route('/my-endpoint', methods=['POST'])
async def my_endpoint():
    # Implementation
    pass
```

2. Registra in `app.py`:
```python
from routes.my_module import my_bp
app.register_blueprint(my_bp)
```
