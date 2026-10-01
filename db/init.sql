CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS faq_embeddings (
    id BIGSERIAL PRIMARY KEY,
    faq_id VARCHAR(20) NOT NULL UNIQUE,
    category TEXT NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
    content_hash CHAR(64) NOT NULL,
    embedding VECTOR(384) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS faq_embeddings_category_idx
    ON faq_embeddings (category);

CREATE INDEX IF NOT EXISTS faq_embeddings_embedding_hnsw_idx
    ON faq_embeddings
    USING hnsw (embedding vector_cosine_ops);
