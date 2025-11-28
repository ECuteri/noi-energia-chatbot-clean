-- Migration: Fix missing content_tsv column for noi_energia_documents
-- This migration ensures the content_tsv column exists for full-text search
-- Run this migration in your Supabase SQL editor if you're seeing:
-- "column content_tsv does not exist" errors

-- Add Full-Text Search column for NOI Energia documents (Italian language)
ALTER TABLE noi_energia_documents
ADD COLUMN IF NOT EXISTS content_tsv tsvector
GENERATED ALWAYS AS (to_tsvector('italian', coalesce(content, ''))) STORED;

-- Create GIN index for Full-Text Search (if it doesn't exist)
CREATE INDEX IF NOT EXISTS idx_noi_energia_content_fts
ON noi_energia_documents USING GIN(content_tsv);

-- Verification query (run after migration to confirm it worked)
-- SELECT column_name, data_type
-- FROM information_schema.columns
-- WHERE table_name = 'noi_energia_documents' AND column_name = 'content_tsv';
