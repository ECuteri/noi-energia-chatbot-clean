import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def load_environment():
    load_dotenv()
    logger.info("Environment variables loaded.")


load_environment()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    logger.critical("FATAL ERROR: OPENROUTER_API_KEY environment variable not set.")
    sys.exit("OPENROUTER_API_KEY not set. Application cannot start.")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

PORT = int(os.getenv("PORT", 5001))

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")

CHATWOOT_BASE_URL = os.getenv("CHATWOOT_BASE_URL")
CHATWOOT_ACCOUNT_ID = os.getenv("CHATWOOT_ACCOUNT_ID")
CHATWOOT_API_ACCESS_TOKEN = os.getenv("CHATWOOT_API_ACCESS_TOKEN")

CHATWOOT_NOI_CER_INBOX_ID = os.getenv("CHATWOOT_NOI_CER_INBOX_ID")
CHATWOOT_NOI_CER_BOT_TOKEN = os.getenv("CHATWOOT_NOI_CER_BOT_TOKEN")
CHATWOOT_NOI_CER_WEBHOOK_SECRET = os.getenv("CHATWOOT_NOI_CER_WEBHOOK_SECRET")

CHATWOOT_NOI_ENERGIA_INBOX_ID = os.getenv("CHATWOOT_NOI_ENERGIA_INBOX_ID")
CHATWOOT_NOI_ENERGIA_BOT_TOKEN = os.getenv("CHATWOOT_NOI_ENERGIA_BOT_TOKEN")
CHATWOOT_NOI_ENERGIA_WEBHOOK_SECRET = os.getenv("CHATWOOT_NOI_ENERGIA_WEBHOOK_SECRET")

DEFAULT_COLLECTION = os.getenv("DEFAULT_COLLECTION", "default")
MAX_SEARCH_RESULTS = int(os.getenv("MAX_SEARCH_RESULTS", "5"))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "1024"))
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.3"))

HYBRID_SEARCH_ENABLED = os.getenv("HYBRID_SEARCH_ENABLED", "true").lower() == "true"
HYBRID_SEARCH_CANDIDATES = int(os.getenv("HYBRID_SEARCH_CANDIDATES", "20"))
RERANK_ENABLED = os.getenv("RERANK_ENABLED", "true").lower() == "true"
RERANK_MODEL = os.getenv("RERANK_MODEL", "cohere/rerank-english-v3.0")
RERANK_TOP_N = int(os.getenv("RERANK_TOP_N", "5"))

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FORMAT_JSON = "%(asctime)s %(name)s %(levelname)s %(message)s"

LOG_LEVELS = {
    "chatbots": os.getenv("CHATBOTS_LOG_LEVEL", "WARNING").upper(),
    "database": os.getenv("DATABASE_LOG_LEVEL", "WARNING").upper(),
    "httpx": os.getenv("HTTPX_LOG_LEVEL", "WARNING").upper(),
    "langchain": os.getenv("LANGCHAIN_LOG_LEVEL", "WARNING").upper(),
    "openai": os.getenv("OPENAI_LOG_LEVEL", "WARNING").upper(),
}

LOG_TO_FILE = os.getenv("LOG_TO_FILE", "true").lower() == "true"
LOG_FILE_PATH = os.getenv("LOG_FILE_PATH", "app.log")
LOG_MAX_SIZE = int(os.getenv("LOG_MAX_SIZE", "10485760"))
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))
LOG_USE_JSON_FORMAT = os.getenv("LOG_USE_JSON_FORMAT", "false").lower() == "true"


class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


def setup_logging():
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    if LOG_USE_JSON_FORMAT:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(LOG_FORMAT)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    file_handler = None
    if LOG_TO_FILE:
        try:
            log_file = Path(LOG_FILE_PATH)
            log_file.parent.mkdir(exist_ok=True)

            from logging.handlers import RotatingFileHandler

            file_handler = RotatingFileHandler(
                LOG_FILE_PATH, maxBytes=LOG_MAX_SIZE, backupCount=LOG_BACKUP_COUNT
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
        except Exception as e:
            logger.warning(f"Failed to set up file logging: {e}")

    root_logger.addHandler(console_handler)
    if file_handler:
        root_logger.addHandler(file_handler)

    root_logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    for module, level in LOG_LEVELS.items():
        if hasattr(logging, level):
            logging.getLogger(module).setLevel(getattr(logging, level))

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("hypercorn").setLevel(logging.WARNING)

    logger.info(
        f"Logging configured with level: {LOG_LEVEL}, file_logging: {LOG_TO_FILE}, json_format: {LOG_USE_JSON_FORMAT}"
    )


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = SCRIPT_DIR
PROMPTS_DIR = os.path.join(PROJECT_ROOT, "prompts")

logger.info(
    f"OpenRouter API Key: {'***' + OPENROUTER_API_KEY[-4:] if OPENROUTER_API_KEY else 'NOT_SET'}"
)
logger.info(
    f"Gemini API Key: {'***' + GEMINI_API_KEY[-4:] if GEMINI_API_KEY else 'NOT_SET'}"
)
logger.info("Transcription Provider: Gemini")
logger.info(f"Supabase URL: {SUPABASE_URL}")
logger.info(f"Embedding model: {EMBEDDING_MODEL} ({EMBEDDING_DIMENSIONS} dimensions)")
logger.info(f"Similarity threshold: {SIMILARITY_THRESHOLD}")
logger.info(f"Hybrid search enabled: {HYBRID_SEARCH_ENABLED}")
logger.info(f"Rerank enabled: {RERANK_ENABLED}, model: {RERANK_MODEL}")
logger.info(
    "Using Supabase for storage: chat_history, noi_cer_documents, noi_energia_documents"
)
logger.info(
    f"Chatwoot Base URL: {CHATWOOT_BASE_URL if CHATWOOT_BASE_URL else 'NOT_SET'}"
)
logger.info(
    f"Chatwoot Account ID: {CHATWOOT_ACCOUNT_ID if CHATWOOT_ACCOUNT_ID else 'NOT_SET'}"
)
logger.info(
    f"Chatwoot NOI CER Inbox ID: {CHATWOOT_NOI_CER_INBOX_ID if CHATWOOT_NOI_CER_INBOX_ID else 'NOT_SET'}"
)
logger.info(
    f"Chatwoot NOI CER Bot Token: {'***' + CHATWOOT_NOI_CER_BOT_TOKEN[-4:] if CHATWOOT_NOI_CER_BOT_TOKEN else 'NOT_SET'}"
)
logger.info(
    f"Chatwoot NOI Energia Inbox ID: {CHATWOOT_NOI_ENERGIA_INBOX_ID if CHATWOOT_NOI_ENERGIA_INBOX_ID else 'NOT_SET'}"
)
logger.info(
    f"Chatwoot NOI Energia Bot Token: {'***' + CHATWOOT_NOI_ENERGIA_BOT_TOKEN[-4:] if CHATWOOT_NOI_ENERGIA_BOT_TOKEN else 'NOT_SET'}"
)
