import asyncio
import logging
import os
import sys

import hypercorn.asyncio
from hypercorn.config import Config as HypercornConfig
from quart import Quart

from config import PORT, load_environment, setup_logging

try:
    from routes.chat_history_routes import chat_history_bp
except Exception:
    chat_history_bp = None

try:
    from routes.local_test import local_test_bp
except Exception:
    local_test_bp = None

load_environment()
setup_logging()
logger = logging.getLogger(__name__)

app = Quart(__name__)
app.debug = os.getenv("APP_DEBUG", "false").lower() == "true"


async def startup_event():
    logger.info("Application startup sequence initiated...")
    logger.info("Using Supabase for all storage (chat history and RAG documents)...")

    logger.info("Initializing Supabase schema...")
    try:
        from database.init_supabase import (
            initialize_supabase_schema,
            verify_supabase_tables,
        )

        await initialize_supabase_schema()
        table_status = await verify_supabase_tables()
        logger.info(f"Supabase tables status: {table_status}")
    except Exception as e:
        logger.warning(f"Supabase schema initialization warning: {e}")
        logger.info(
            "If tables don't exist, please run the SQL from database/init_supabase.py"
        )

    logger.info("Initializing Noi CER chatbot...")
    try:
        from chatbots.noi_cer_chatbot.agent import create_noi_cer_chatbot_agent

        noi_cer_chatbot = await create_noi_cer_chatbot_agent()
        app.config["NOI_CER_CHATBOT"] = noi_cer_chatbot
        logger.info("Noi CER chatbot initialized successfully.")
    except Exception as e:
        logger.critical(f"Failed to initialize Noi CER chatbot: {e}", exc_info=True)
        sys.exit("Noi CER chatbot initialization failed.")

    logger.info("Initializing Noi Energia chatbot...")
    try:
        from chatbots.noi_energia_chatbot.agent import create_noi_energia_chatbot_agent

        noi_energia_chatbot = await create_noi_energia_chatbot_agent()
        app.config["NOI_ENERGIA_CHATBOT"] = noi_energia_chatbot
        logger.info("Noi Energia chatbot initialized successfully.")
    except Exception as e:
        logger.critical(f"Failed to initialize Noi Energia chatbot: {e}", exc_info=True)
        sys.exit("Noi Energia chatbot initialization failed.")

    logger.info("Application startup completed.")


async def shutdown_event():
    logger.info("Application shutdown sequence initiated...")
    logger.info("Application shutdown completed.")


app.before_serving(startup_event)
app.after_serving(shutdown_event)

if chat_history_bp is not None:
    app.register_blueprint(chat_history_bp)

if local_test_bp is not None:
    app.register_blueprint(local_test_bp)

try:
    from routes.chatwoot_webhook import chatwoot_webhook_bp

    app.register_blueprint(chatwoot_webhook_bp)
    logger.info("Chatwoot webhook routes registered")
except Exception as e:
    logger.warning(f"Chatwoot webhook routes not available: {e}")

logger.info("Quart app initialized and blueprints registered.")

if __name__ == "__main__":
    try:
        logger.info(f"Starting Hypercorn server on 0.0.0.0:{PORT}")
        hypercorn_config = HypercornConfig()
        hypercorn_config.bind = [f"0.0.0.0:{PORT}"]
        asyncio.run(hypercorn.asyncio.serve(app, hypercorn_config))
    except KeyboardInterrupt:
        logger.info("Server stopped by user (KeyboardInterrupt).")
    except Exception as e:
        logger.critical(f"Fatal error during server execution: {str(e)}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Server has shut down.")
