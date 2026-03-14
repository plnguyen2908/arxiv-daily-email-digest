PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS papers (
    arxiv_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    abstract TEXT,
    paper_url TEXT,
    pdf_url TEXT,
    published_at TEXT,
    updated_at TEXT,
    primary_category TEXT,
    categories_csv TEXT,
    extracted_text_hash TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS keyword_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT NOT NULL,
    arxiv_id TEXT NOT NULL,
    title_corr REAL NOT NULL DEFAULT 0.0,
    abstract_corr REAL NOT NULL DEFAULT 0.0,
    full_text_corr REAL NOT NULL DEFAULT 0.0,
    category_bonus REAL NOT NULL DEFAULT 0.0,
    total_corr REAL NOT NULL DEFAULT 0.0,
    run_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(arxiv_id) REFERENCES papers(arxiv_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_keyword_scores_keyword_total
ON keyword_scores(keyword, total_corr DESC);

CREATE TABLE IF NOT EXISTS sent_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT NOT NULL,
    arxiv_id TEXT NOT NULL,
    sent_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    run_id TEXT,
    FOREIGN KEY(arxiv_id) REFERENCES papers(arxiv_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sent_log_keyword_arxiv
ON sent_log(keyword, arxiv_id);

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    status TEXT NOT NULL,
    notes TEXT
);

