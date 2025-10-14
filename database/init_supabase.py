import logging
from typing import Optional

from services.supabase_client import supabase_store

logger = logging.getLogger(__name__)


async def migrate_uuid_to_text() -> bool:
    """
    Migrate existing tables from UUID to TEXT for id columns.
    This is needed to support Google Drive file IDs and other external identifiers.

    Returns:
        bool: True if migration successful or not needed, False otherwise
    """
    try:
        pool = await supabase_store._get_connection()
        if not pool:
            logger.error("Supabase connection pool not initialized. Cannot migrate.")
            return False

        async with pool.acquire() as conn:
            tables_to_migrate = [
                ("noi_cer_documents", "noi_cer_documents_metadata"),
                ("noi_energia_documents", "noi_energia_documents_metadata"),
            ]

            for doc_table, meta_table in tables_to_migrate:
                try:
                    result = await conn.fetchval(
                        f"SELECT data_type FROM information_schema.columns WHERE table_name = '{doc_table}' AND column_name = 'id'"
                    )

                    if result == "uuid":
                        logger.info(f"Migrating {doc_table} from UUID to TEXT...")

                        await conn.execute(f"DROP TABLE IF EXISTS {doc_table} CASCADE")
                        await conn.execute(f"DROP TABLE IF EXISTS {meta_table} CASCADE")

                        logger.info(
                            f"✅ Dropped existing {doc_table} and {meta_table} tables"
                        )
                    elif result == "text":
                        logger.info(f"✅ {doc_table} already uses TEXT for id column")
                    elif result is None:
                        logger.info(f"✅ {doc_table} does not exist yet")

                except Exception as e:
                    logger.warning(f"Could not check {doc_table}: {e}")

        return True

    except Exception as e:
        logger.error(f"Error during migration: {e}", exc_info=True)
        return False


async def initialize_supabase_schema() -> bool:
    """
    Initialize Supabase database schema.
    Creates tables if they don't exist, adds missing columns if needed.

    Expected tables:
    1. chat_history - for conversation storage (shared by both chatbots)
    2. noi_cer_documents_metadata - document metadata for Noi CER
    3. noi_cer_documents - document chunks with embeddings for Noi CER
    4. noi_energia_documents_metadata - document metadata for Noi Energia
    5. noi_energia_documents - document chunks with embeddings for Noi Energia

    Note: Documents and metadata tables are independent:
    - Metadata stores one row per source file (Google Drive file ID)
    - Documents stores multiple chunks per file with vector embeddings
    - Documents reference file_id via JSONB metadata field, not foreign key

    Returns:
        bool: True if initialization successful, False otherwise
    """
    try:
        logger.info("Starting Supabase schema initialization...")

        pool = await supabase_store._get_connection()

        if not pool:
            logger.error(
                "Supabase connection pool not initialized. Cannot create schema."
            )
            return False

        logger.info("✅ Supabase connection established")

        logger.info("Checking for schema migrations...")
        await migrate_uuid_to_text()

        async with pool.acquire() as conn:
            try:
                logger.info("Enabling pgvector extension...")
                await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                logger.info("✅ pgvector extension enabled")
            except Exception as e:
                logger.warning(f"⚠️  Could not enable pgvector extension: {e}")
                logger.info("You may need to enable it manually via Supabase dashboard")

            logger.info("Creating tables if they don't exist...")

            try:
                await conn.execute(_get_table_creation_sql())
                logger.info("✅ All tables and indexes created successfully")

                tables_created = await _verify_tables_created(conn)
                if tables_created:
                    logger.info("✅ Schema initialization completed successfully")
                    return True
                else:
                    logger.warning("⚠️  Some tables may not have been created properly")
                    return False

            except Exception as e:
                logger.error(f"Error creating tables: {e}", exc_info=True)
                return False

    except Exception as e:
        logger.error(f"Error during Supabase schema initialization: {e}", exc_info=True)
        return False


async def _verify_tables_created(conn) -> bool:
    """
    Verify that all required tables were created.

    Args:
        conn: Database connection

    Returns:
        bool: True if all tables exist, False otherwise
    """
    required_tables = [
        "chat_history",
        "noi_cer_documents",
        "noi_cer_documents_metadata",
        "noi_energia_documents",
        "noi_energia_documents_metadata",
    ]

    all_exist = True
    for table_name in required_tables:
        try:
            await conn.fetchval(f"SELECT 1 FROM {table_name} LIMIT 1")
            logger.info(f"  ✅ Table '{table_name}' verified")
        except Exception:
            logger.error(f"  ❌ Table '{table_name}' not found")
            all_exist = False

    return all_exist


def _get_table_creation_sql() -> str:
    return """
-- Enable pgvector extension (if not already enabled)
CREATE EXTENSION IF NOT EXISTS vector;

-- Chat History Table (shared by both chatbots)
CREATE TABLE IF NOT EXISTS chat_history (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_history_session_created
ON chat_history (session_id, created_at);

-- Noi CER Documents Metadata Table
CREATE TABLE IF NOT EXISTS noi_cer_documents_metadata (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_noi_cer_metadata_created
ON noi_cer_documents_metadata (created_at DESC);

-- Noi CER Documents Table (vector store managed)
CREATE TABLE IF NOT EXISTS noi_cer_documents (
    id TEXT PRIMARY KEY,
    metadata JSONB DEFAULT '{}',
    embedding VECTOR(1536),
    content TEXT
);

-- Trigger to auto-generate ID if NULL
CREATE OR REPLACE FUNCTION generate_noi_cer_doc_id()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.id IS NULL THEN
        NEW.id := gen_random_uuid()::text;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS noi_cer_documents_id_trigger ON noi_cer_documents;
CREATE TRIGGER noi_cer_documents_id_trigger
    BEFORE INSERT ON noi_cer_documents
    FOR EACH ROW
    EXECUTE FUNCTION generate_noi_cer_doc_id();

CREATE INDEX IF NOT EXISTS idx_noi_cer_documents_embedding
ON noi_cer_documents USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Noi Energia Documents Metadata Table
CREATE TABLE IF NOT EXISTS noi_energia_documents_metadata (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_noi_energia_metadata_created
ON noi_energia_documents_metadata (created_at DESC);

-- Noi Energia Documents Table (vector store managed)
CREATE TABLE IF NOT EXISTS noi_energia_documents (
    id TEXT PRIMARY KEY,
    metadata JSONB DEFAULT '{}',
    embedding VECTOR(1536),
    content TEXT
);

-- Trigger to auto-generate ID if NULL
CREATE OR REPLACE FUNCTION generate_noi_energia_doc_id()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.id IS NULL THEN
        NEW.id := gen_random_uuid()::text;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS noi_energia_documents_id_trigger ON noi_energia_documents;
CREATE TRIGGER noi_energia_documents_id_trigger
    BEFORE INSERT ON noi_energia_documents
    FOR EACH ROW
    EXECUTE FUNCTION generate_noi_energia_doc_id();

CREATE INDEX IF NOT EXISTS idx_noi_energia_documents_embedding
ON noi_energia_documents USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
"""


async def verify_supabase_tables() -> dict:
    """
    Verify that all required Supabase tables exist.

    Returns:
        dict: Status of each required table
    """
    pool = await supabase_store._get_connection()
    if not pool:
        logger.error("Supabase connection pool not initialized")
        return {}

    required_tables = [
        "chat_history",
        "noi_cer_documents",
        "noi_cer_documents_metadata",
        "noi_energia_documents",
        "noi_energia_documents_metadata",
    ]

    table_status = {}

    async with pool.acquire() as conn:
        for table_name in required_tables:
            try:
                await conn.fetchval(f"SELECT 1 FROM {table_name} LIMIT 1")
                table_status[table_name] = "exists"
                logger.info(f"✅ Table '{table_name}' exists")
            except Exception as e:
                table_status[table_name] = f"error: {str(e)}"
                logger.warning(f"⚠️  Table '{table_name}' check failed: {e}")

    return table_status


def print_setup_instructions():
    print("\n" + "=" * 80)
    print("SUPABASE DATABASE SETUP INSTRUCTIONS")
    print("=" * 80)
    print("\n1. Go to your Supabase project dashboard")
    print("2. Navigate to the SQL Editor")
    print("3. Copy and paste the following SQL:")
    print("\n" + "-" * 80)
    print(_get_table_creation_sql())
    print("-" * 80)
    print("\n4. Run the SQL to create all required tables")
    print("5. Verify tables were created in the Table Editor")
    print("\n" + "=" * 80 + "\n")
