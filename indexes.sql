-- indexes.sql: search indexes, created AFTER a bulk load.
-- Building an index once at the end is much faster than updating it on every insert.
-- Replace the two CREATE INDEX lines with the exact ones you ran locally. To see them, run on local:
--   SELECT indexdef FROM pg_indexes WHERE tablename = 'chunks';

SET LOCAL maintenance_work_mem = '256MB';  -- more memory = faster HNSW build; this transaction only

CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw
    ON chunks USING hnsw (embedding halfvec_cosine_ops);

CREATE INDEX IF NOT EXISTS chunks_tsv_gin
    ON chunks USING gin (tsv);

-- Fresh statistics so the query planner knows the tables are big now.
ANALYZE documents;
ANALYZE chunks;
