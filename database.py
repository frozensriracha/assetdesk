"""SQLite connections and reproducible, non-destructive initialization."""
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parent


def connect(path):
    # mode=rw prevents a mistyped path from creating an empty database.
    db = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=rw', uri=True, timeout=5)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys = ON')
    return db


def initialize(path):
    if sqlite3.sqlite_version_info < (3, 37, 0):
        raise ValueError('SQLite 3.37 or newer is required. Install a newer Python build.')
    path = Path(path).resolve()
    # exclusive creation protects an existing database, including on repeated setup
    with path.open('xb'):
        pass
    try:
        db = connect(path)
        try:
            for filename in ('schema.sql', 'insert_data.sql'):
                db.executescript((ROOT / filename).read_text(encoding='utf-8'))
            if db.execute('PRAGMA foreign_key_check').fetchall():
                raise ValueError('Sample data failed foreign-key validation.')
        finally:
            db.close()
    except Exception:
        path.unlink()
        raise
