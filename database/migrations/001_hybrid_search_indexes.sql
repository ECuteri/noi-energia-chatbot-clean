-- Migration: Add Full-Text Search and HNSW indexes for improved RAG retrieval
-- Run this migration in your Supabase SQL editor

-- ============================================================================
-- STEP 1: Add Full-Text Search columns (Italian language)
-- ============================================================================

-- NOI Energia documents
ALTER TABLE noi_energia_documents
ADD COLUMN IF NOT EXISTS content_tsv tsvector
GENERATED ALWAYS AS (to_tsvector('italian', coalesce(content, ''))) STORED;

-- NOI CER documents
ALTER TABLE noi_cer_documents
ADD COLUMN IF NOT EXISTS content_tsv tsvector
GENERATED ALWAYS AS (to_tsvector('italian', coalesce(content, ''))) STORED;

-- ============================================================================
-- STEP 2: Create GIN indexes for Full-Text Search
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_noi_energia_content_fts
ON noi_energia_documents USING GIN(content_tsv);

CREATE INDEX IF NOT EXISTS idx_noi_cer_content_fts
ON noi_cer_documents USING GIN(content_tsv);

-- ============================================================================
-- STEP 3: Upgrade vector indexes from IVFFlat to HNSW (better recall)
-- ============================================================================

-- Drop old IVFFlat indexes
DROP INDEX IF EXISTS idx_noi_energia_documents_embedding;
DROP INDEX IF EXISTS idx_noi_cer_documents_embedding;

-- Create HNSW indexes (3072 dimensions for text-embedding-3-large)
-- Note: m=16 and ef_construction=64 are good defaults for quality/speed tradeoff
CREATE INDEX idx_noi_energia_documents_embedding
ON noi_energia_documents
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

CREATE INDEX idx_noi_cer_documents_embedding
ON noi_cer_documents
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- ============================================================================
-- STEP 4: Update vector dimension (if changing from 1536 to 1024)
-- ============================================================================

-- IMPORTANT: Supabase has a 2000 dimension limit for indexes, so we use 1024 dimensions
-- (text-embedding-3-large with dimensions=1024 parameter)
-- This is still better quality than text-embedding-3-small (1536) because it's from the large model
-- This will clear existing embeddings!

-- Run these commands to upgrade to 1024 dimensions:

-- ALTER TABLE noi_energia_documents
-- ALTER COLUMN embedding TYPE vector(1024);

-- ALTER TABLE noi_cer_documents
-- ALTER COLUMN embedding TYPE vector(1024);

-- ============================================================================
-- Verification queries (run after migration)
-- ============================================================================

-- Check FTS column exists
-- SELECT column_name, data_type
-- FROM information_schema.columns
-- WHERE table_name = 'noi_energia_documents' AND column_name = 'content_tsv';

-- Check indexes
-- SELECT indexname, indexdef
-- FROM pg_indexes
-- WHERE tablename IN ('noi_energia_documents', 'noi_cer_documents');

-- Test FTS search
-- SELECT id, ts_rank(content_tsv, plainto_tsquery('italian', 'energia')) as rank
-- FROM noi_energia_documents
-- WHERE content_tsv @@ plainto_tsquery('italian', 'energia')
-- ORDER BY rank DESC
-- LIMIT 5;
