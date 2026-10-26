-- schema.sql
-- Creates the two tables of the Investigation Engine. Safe to run more than once.
-- Run with: python -m scripts.init_db            (local)
--           python -m scripts.init_db .env.neon  (Neon)

CREATE EXTENSION IF NOT EXISTS vector;  -- halfvec needs pgvector 0.7.0+

-- One row per document: a HotpotQA paragraph, a company file or an uploaded file.
CREATE TABLE IF NOT EXISTS documents (
    id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    source        text        NOT NULL,                -- 'hotpotqa', 'company' or 'upload'
    external_id   text        NOT NULL,                -- id inside its source (paragraph id or file name)
    title         text        NOT NULL,
    file_format   text        NOT NULL,                -- 'pdf', 'docx', 'txt' or 'md'
    content_hash  text        NOT NULL UNIQUE,         -- SHA-256 of the normalized text: same hash = duplicate
    version       integer     NOT NULL DEFAULT 1,      -- +1 when a file with the same name is re-uploaded
    is_protected  boolean     NOT NULL DEFAULT false,  -- true for the seed corpus: DELETE is refused
    metadata      jsonb       NOT NULL DEFAULT '{}'::jsonb,  -- file name, page count, author, ...
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),  -- set by the app on update (no trigger)
    UNIQUE (source, external_id)                       -- lets "same file name" mean update, not insert
);

-- One row per chunk. Deleting a document deletes its chunks (ON DELETE CASCADE).
CREATE TABLE IF NOT EXISTS chunks (
    id           bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,  -- chunk_id in citations
    document_id  uuid         NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    chunk_index  integer      NOT NULL,                -- 0, 1, 2 ... position inside the document
    strategy     text         NOT NULL CHECK (strategy IN ('paragraph', 'fixed')),
    text         text         NOT NULL,                -- starts with 'Title: ...'
    text_hash    text         NOT NULL,                -- SHA-256 of text, key for the embedding cache
    embedding    halfvec(384) NOT NULL,                -- bge-small-en-v1.5, stored in 16-bit floats
    tsv          tsvector     GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,  -- keyword search
    metadata     jsonb        NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (document_id, strategy, chunk_index)        -- its index also serves the cascade delete
);

-- Day 2, AFTER the bulk load (building an index once on a full table is much
-- faster than updating it on every insert). Not run by init_db yet:
--
-- CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw ON chunks USING hnsw (embedding halfvec_cosine_ops);
-- CREATE INDEX IF NOT EXISTS chunks_tsv_gin ON chunks USING gin (tsv);
