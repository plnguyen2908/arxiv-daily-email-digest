from __future__ import annotations

import sqlite3
from pathlib import Path


def _default_schema_path() -> Path:
    return Path(__file__).resolve().parent / "schema.sql"


def init_db(db_path: Path, schema_path: Path | None = None) -> None:
    schema_file = schema_path or _default_schema_path()
    schema_sql = schema_file.read_text(encoding="utf-8")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(schema_sql)
        conn.commit()

