#!/bin/bash

set -e

echo "🚀 Script di Deployment Chatbot NoiEnergia"
echo "==========================================="

check_docker() {
    if ! command -v docker &> /dev/null; then
        echo "❌ Docker non trovato. Per favore installa Docker prima."
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        echo "❌ docker-compose non trovato. Per favore installa docker-compose prima."
        exit 1
    fi

    if [ "$USE_SUDO" != true ] && ! docker ps &> /dev/null; then
        echo "⚠️  Rilevato problema permessi Docker."
        echo ""
        echo "🔧 Per risolvere, scegli una delle seguenti opzioni:"
        echo ""
        echo "Opzione 1 - Aggiungi utente al gruppo docker (raccomandato):"
        echo "   sudo usermod -aG docker \$USER"
        echo "   # Poi effettua logout e login nuovamente, o esegui: newgrp docker"
        echo ""
        echo "Opzione 2 - Esegui questo script con sudo:"
        echo "   sudo ./deploy.sh"
        echo ""
        read -p "Inserisci 1 o 2: " choice

        case $choice in
            1)
                echo "Aggiunta utente al gruppo docker..."
                sudo usermod -aG docker $USER
                echo "✅ Utente aggiunto al gruppo docker."
                echo "🔄 Per favore effettua logout e login nuovamente, poi esegui nuovamente questo script."
                exit 0
                ;;
            2)
                echo "Esecuzione con sudo..."
                if [ "$EUID" -eq 0 ]; then
                    echo "Già in esecuzione come root."
                else
                    echo "Per favore esegui: sudo ./deploy.sh"
                    exit 1
                fi
                ;;
            *)
                echo "❌ Scelta non valida. Per favore esegui nuovamente lo script."
                exit 1
                ;;
        esac
    fi
}

create_env_file() {
    if [ ! -f ".env" ]; then
        echo "📝 Creazione template file .env..."
        cat > .env << 'EOF'
OPENAI_API_KEY=your-openai-api-key-here
GROQ_API_KEY=your-groq-api-key-here
GEMINI_API_KEY=your-gemini-api-key-here

TRANSCRIPTION_PROVIDER=gemini

PORT=5001
RUN_CONTEXT=APP

SUPABASE_URL=your-supabase-url-here
SUPABASE_API_KEY=your-supabase-api-key-here

CHATWOOT_BASE_URL=https://noienergia-chat.infrastrutture.ai
CHATWOOT_ACCOUNT_ID=your-chatwoot-account-id
CHATWOOT_API_ACCESS_TOKEN=your-chatwoot-api-token

CHATWOOT_NOI_CER_INBOX_ID=your-noi-cer-inbox-id
CHATWOOT_NOI_CER_BOT_TOKEN=your-noi-cer-bot-token
CHATWOOT_NOI_CER_WEBHOOK_SECRET=your-noi-cer-webhook-secret

CHATWOOT_NOI_ENERGIA_INBOX_ID=your-noi-energia-inbox-id
CHATWOOT_NOI_ENERGIA_BOT_TOKEN=your-noi-energia-bot-token
CHATWOOT_NOI_ENERGIA_WEBHOOK_SECRET=your-noi-energia-webhook-secret

DEFAULT_COLLECTION=default
MAX_SEARCH_RESULTS=10
EMBEDDING_MODEL=text-embedding-3-small
SIMILARITY_THRESHOLD=0.3

LOG_LEVEL=INFO
CHATBOTS_LOG_LEVEL=WARNING
DATABASE_LOG_LEVEL=WARNING
HTTPX_LOG_LEVEL=WARNING
LANGCHAIN_LOG_LEVEL=WARNING
OPENAI_LOG_LEVEL=WARNING
EOF
        echo "✅ Template file .env creato."
        echo ""
        echo "⚠️  IMPORTANTE: Modifica .env con i tuoi valori effettivi prima del deployment!"
        echo "   Richiesti: OPENAI_API_KEY, GROQ_API_KEY, GEMINI_API_KEY, SUPABASE_URL, SUPABASE_API_KEY"
        echo "   Richieste: Tutte le variabili d'ambiente CHATWOOT_*"
        exit 1
    fi
}

validate_env_file() {
    echo "🔍 Validazione file .env..."

    local required_vars=(
        "OPENAI_API_KEY"
        "GROQ_API_KEY"
        "GEMINI_API_KEY"
        "SUPABASE_URL"
        "SUPABASE_API_KEY"
        "CHATWOOT_BASE_URL"
        "CHATWOOT_ACCOUNT_ID"
    )

    local missing_vars=()

    for var in "${required_vars[@]}"; do
        if ! grep -q "^${var}=.\+" .env 2>/dev/null; then
            missing_vars+=("$var")
        elif grep -q "^${var}=your-" .env 2>/dev/null; then
            missing_vars+=("$var (rilevato valore placeholder)")
        fi
    done

    if [ ${#missing_vars[@]} -ne 0 ]; then
        echo "❌ Variabili d'ambiente richieste mancanti o non valide:"
        for var in "${missing_vars[@]}"; do
            echo "   - $var"
        done
        echo ""
        echo "Aggiorna il tuo file .env con valori effettivi."
        exit 1
    fi

    echo "✅ File ambiente validato."
}

get_docker_compose_cmd() {
    if command -v docker-compose &> /dev/null; then
        echo "docker-compose"
    else
        echo "docker compose"
    fi
}

deploy() {
    echo "🚀 Deployment container chatbot..."

    local compose_cmd=$(get_docker_compose_cmd)

    if [ "$USE_SUDO" = true ]; then
        sudo $compose_cmd build
        sudo $compose_cmd up -d
    else
        $compose_cmd build
        $compose_cmd up -d
    fi

    echo ""
    echo "✅ Deployment completato!"
    echo ""
    echo "📋 Prossimi passi:"
    echo "   1. Assicurati che nginx sia configurato per proxy degli endpoint chatbot"
    echo "   2. Vedi nginx_chatbot_routes.conf per configurazione route"
    echo "   3. Ricarica nginx: sudo systemctl reload nginx"
    echo "   4. Testa endpoint webhook:"
    echo "      - https://noienergia-chat.infrastrutture.ai/chatwoot/webhook/noi-cer"
    echo "      - https://noienergia-chat.infrastrutture.ai/chatwoot/webhook/noi-energia"
    echo ""
    echo "📊 Controlla stato deployment con: ./deploy.sh status"
}

stop() {
    echo "🛑 Arresto container chatbot..."

    local compose_cmd=$(get_docker_compose_cmd)

    if [ "$USE_SUDO" = true ]; then
        sudo $compose_cmd down
    else
        $compose_cmd down
    fi

    echo "✅ Container arrestato."
}

restart() {
    echo "🔄 Riavvio container chatbot..."

    local compose_cmd=$(get_docker_compose_cmd)

    if [ "$USE_SUDO" = true ]; then
        sudo $compose_cmd restart
    else
        $compose_cmd restart
    fi

    echo "✅ Container riavviato."
}

show_logs() {
    echo "📜 Visualizzazione log container (Ctrl+C per uscire)..."
    echo ""

    local compose_cmd=$(get_docker_compose_cmd)

    if [ "$USE_SUDO" = true ]; then
        sudo $compose_cmd logs -f --tail=100
    else
        $compose_cmd logs -f --tail=100
    fi
}

show_status() {
    echo "📊 Stato Container:"
    echo ""

    local compose_cmd=$(get_docker_compose_cmd)

    if [ "$USE_SUDO" = true ]; then
        sudo $compose_cmd ps
        echo ""
        echo "📈 Health Check:"
        sudo docker inspect noienergia-chatbot --format='{{.State.Health.Status}}' 2>/dev/null || echo "Health check non disponibile"
    else
        $compose_cmd ps
        echo ""
        echo "📈 Health Check:"
        docker inspect noienergia-chatbot --format='{{.State.Health.Status}}' 2>/dev/null || echo "Health check non disponibile"
    fi
}

rebuild() {
    echo "🔨 Ricostruzione e redeployment container chatbot..."

    local compose_cmd=$(get_docker_compose_cmd)

    if [ "$USE_SUDO" = true ]; then
        sudo $compose_cmd down
        sudo $compose_cmd build --no-cache
        sudo $compose_cmd up -d
    else
        $compose_cmd down
        $compose_cmd build --no-cache
        $compose_cmd up -d
    fi

    echo "✅ Ricostruzione completata."
}

main() {
    check_docker
    create_env_file

    echo ""
    echo "Scegli un'azione:"
    echo "1) Deploy chatbot"
    echo "2) Arresta chatbot"
    echo "3) Riavvia chatbot"
    echo "4) Mostra log"
    echo "5) Mostra stato"
    echo "6) Ricostruisci e redeploy"
    echo ""
    read -p "Inserisci la tua scelta (1-6): " choice

    case $choice in
        1)
            validate_env_file
            deploy
            ;;
        2)
            stop
            ;;
        3)
            restart
            ;;
        4)
            show_logs
            ;;
        5)
            show_status
            ;;
        6)
            validate_env_file
            rebuild
            ;;
        *)
            echo "❌ Scelta non valida. Per favore esegui nuovamente lo script."
            exit 1
            ;;
    esac
}

main
