-- PostgreSQL Schema for Dovos Chat Archive
-- Single-store architecture with conversations, messages, FTS, and vectors

-- Ensure required extensions are available
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS vector;

-- ========== Core Tables ==========

-- Conversations table
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Messages table with versioning for embedding staleness detection
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    version INTEGER NOT NULL DEFAULT 1
);

-- Generated column for full-text search (eliminates app-level sync)
ALTER TABLE messages ADD COLUMN message_search TSVECTOR 
    GENERATED ALWAYS AS (to_tsvector('english', coalesce(content, ''))) STORED;

-- Message embeddings table (separate for async generation and multiple models)
CREATE TABLE message_embeddings (
    message_id UUID PRIMARY KEY REFERENCES messages(id) ON DELETE CASCADE,
    embedding VECTOR(384), -- Default for all-MiniLM-L6-v2, adjust based on EMBEDDING_DIM
    model TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Job queue table using Postgres as the queue
CREATE TABLE jobs (
    id BIGSERIAL PRIMARY KEY,
    kind TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    attempts INTEGER NOT NULL DEFAULT 0,
    not_before TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ========== Indexes ==========

-- Conversations indexes
CREATE INDEX idx_conversations_created_at ON conversations(created_at DESC);
CREATE INDEX idx_conversations_updated_at ON conversations(updated_at DESC);

-- Messages indexes
CREATE INDEX idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX idx_messages_conv_created ON messages(conversation_id, created_at DESC);
CREATE INDEX idx_messages_created_at ON messages(created_at DESC);
CREATE INDEX idx_messages_role ON messages(role);

-- Full-text search indexes
CREATE INDEX idx_messages_fts ON messages USING GIN (message_search);
CREATE INDEX idx_messages_trgm ON messages USING GIN (content gin_trgm_ops);

-- Vector search index (will be created after data is loaded)
-- Note: IVFFLAT requires ANALYZE and sufficient rows; fallback to flat scan for small datasets
-- CREATE INDEX idx_embeddings_vector ON message_embeddings USING IVFFLAT (embedding) WITH (lists = 100);

-- Job queue indexes
CREATE INDEX idx_jobs_status_kind ON jobs(status, kind);
CREATE INDEX idx_jobs_not_before ON jobs(not_before) WHERE status = 'pending';
CREATE INDEX idx_jobs_created_at ON jobs(created_at DESC);

-- Embeddings indexes
CREATE INDEX idx_embeddings_model ON message_embeddings(model);
CREATE INDEX idx_embeddings_updated_at ON message_embeddings(updated_at DESC);

-- ========== Functions and Triggers ==========

-- Auto-update updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply timestamp triggers
CREATE TRIGGER update_conversations_updated_at BEFORE UPDATE ON conversations 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_messages_updated_at BEFORE UPDATE ON messages 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_jobs_updated_at BEFORE UPDATE ON jobs 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_message_embeddings_updated_at BEFORE UPDATE ON message_embeddings 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ========== Version Management ==========

-- Increment message version on content update (for embedding staleness detection)
CREATE OR REPLACE FUNCTION increment_message_version()
RETURNS TRIGGER AS $$
BEGIN
    -- Only increment version if content actually changed
    IF OLD.content != NEW.content THEN
        NEW.version = OLD.version + 1;
        NEW.updated_at = NOW();
    END IF;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER increment_message_version_trigger BEFORE UPDATE ON messages 
    FOR EACH ROW EXECUTE FUNCTION increment_message_version();

-- ========== Helper Views ==========

-- View for conversation summaries with message counts and date ranges
CREATE VIEW conversation_summaries AS
SELECT 
    c.id,
    c.title,
    c.created_at,
    c.updated_at,
    COUNT(m.id) as message_count,
    MIN(m.created_at) as earliest_message_at,
    MAX(m.created_at) as latest_message_at,
    -- Preview from first message (limited to 200 chars)
    LEFT(COALESCE(
        (SELECT content FROM messages WHERE conversation_id = c.id ORDER BY created_at LIMIT 1),
        ''
    ), 200) as preview
FROM conversations c
LEFT JOIN messages m ON c.id = m.conversation_id
GROUP BY c.id, c.title, c.created_at, c.updated_at;

-- View for embedding coverage
CREATE VIEW embedding_coverage AS
SELECT 
    COUNT(m.id) as total_messages,
    COUNT(e.message_id) as embedded_messages,
    ROUND(COUNT(e.message_id)::numeric / NULLIF(COUNT(m.id), 0) * 100, 2) as coverage_percent,
    COUNT(CASE WHEN e.updated_at < m.updated_at THEN 1 END) as stale_embeddings
FROM messages m
LEFT JOIN message_embeddings e ON m.id = e.message_id;

-- ========== Sample Data Setup (for development) ==========

-- Insert sample conversation (commented out for production)
/*
INSERT INTO conversations (id, title) VALUES 
    ('550e8400-e29b-41d4-a716-446655440000', 'Sample Conversation');

INSERT INTO messages (conversation_id, role, content) VALUES 
    ('550e8400-e29b-41d4-a716-446655440000', 'user', 'Hello, how can I learn PostgreSQL?'),
    ('550e8400-e29b-41d4-a716-446655440000', 'assistant', 'PostgreSQL is a powerful open-source relational database. Here are some great ways to learn...');
*/

-- ========== Performance Notes ==========

/*
Performance considerations for small scale (< 100k messages):

1. IVFFLAT index: Only create after you have >1000 vectors and run ANALYZE
   ALTER TABLE message_embeddings ALTER COLUMN embedding TYPE VECTOR(384);
   ANALYZE message_embeddings;
   CREATE INDEX idx_embeddings_vector ON message_embeddings USING IVFFLAT (embedding) WITH (lists = 100);

2. For tiny datasets, vector similarity can use sequential scan which is often faster

3. pg_trgm works well immediately and provides fuzzy text matching

4. Generated tsvector column eliminates sync issues between app and search index

5. Job queue with FOR UPDATE SKIP LOCKED provides excellent concurrency

6. Hybrid search combines lexical (tsvector) + semantic (vector) ranking
*/