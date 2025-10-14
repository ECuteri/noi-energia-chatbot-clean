# Directory Prompts

I prompt di sistema per tutti i chatbot sono archiviati come file di testo in questa directory per facile manutenzione e controllo versione.

## Prompt Correnti

### Chatbot Noi CER
File: `prompts/noi_cer_chatbot.txt`
Caricato da: `chatbots/noi_cer_chatbot/agent.py`

Il prompt di sistema definisce del chatbot:
- Identità e ruolo come Assistente Noi CER
- Tool disponibili e loro utilizzo
- Linee guida per interazione
- Focus sulla documentazione Noi CER

### Chatbot Noi Energia
File: `prompts/noi_energia_chatbot.txt`
Caricato da: `chatbots/noi_energia_chatbot/agent.py`

Il prompt di sistema definisce del chatbot:
- Identità e ruolo come Assistente Noi Energia
- Tool disponibili e loro utilizzo
- Linee guida per interazione
- Focus sulla documentazione Noi Energia

## Struttura Prompt

Ogni prompt chatbot include:

1. **Identità**: Chi è il chatbot
2. **Tool**: Quali tool sono disponibili
3. **Linee Guida**: Come utilizzare efficacemente i tool
4. **Comportamento**: Come interagire con gli utenti

## Modifica Prompt

Per modificare il comportamento di un chatbot, modifica il corrispondente file di testo nella directory `prompts/`:

- **Chatbot Noi CER**: Modifica `prompts/noi_cer_chatbot.txt`
- **Chatbot Noi Energia**: Modifica `prompts/noi_energia_chatbot.txt`

Le modifiche a questi file saranno automaticamente caricate quando l'agente chatbot viene inizializzato.

Esempio:
```
You are Noi CER Assistant...

Your role is to assist users by providing information...

Guidelines:
- Start by understanding what the user needs
- Use vector_search to find relevant documents
...
```

## Migliori Pratiche

### Design Prompt
- Sii specifico sulle capacità del chatbot
- Descrivi chiaramente ogni tool disponibile
- Fornisci esempi di buoni pattern di utilizzo
- Includi indicazioni per gestione errori

### Istruzioni Tool
- Spiega quando utilizzare ogni tool
- Descrivi gli output attesi
- Fornisci esempi di utilizzo
- Chiarisci limitazioni tool

### Linee Guida Conversazione
- Definisci tono e stile
- Specifica come gestire casi limite
- Includi comportamenti fallback
- Imposta confini e limitazioni


## Testing Prompt

Testa modifiche prompt interagendo con il chatbot:

```bash
curl -X POST http://localhost:5001/local-chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test",
    "message": "Il tuo messaggio di test",
    "chatbot": "noi_cer"
  }'
```

## Controllo Versione

Quando aggiorni prompt:
1. Testa cambiamenti thoroughly
2. Documenta modifiche prompt significative
3. Mantieni prompt focalizzati e concisi
4. Mantieni consistenza tra chatbot
