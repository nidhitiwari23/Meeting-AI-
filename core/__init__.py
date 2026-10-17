"""MeetingAI core package.

Some hosts (older Streamlit Cloud images) ship a SQLite that is too old for ChromaDB (needs >= 3.35).
If that is the case and ``pysqlite3-binary`` is installed, transparently use it instead.
"""
import sqlite3 as _sqlite3
import sys as _sys

if tuple(int(x) for x in _sqlite3.sqlite_version.split(".")[:2]) < (3, 35):  # pragma: no cover
    try:
        import pysqlite3  # type: ignore

        _sys.modules["sqlite3"] = pysqlite3
    except Exception:
        pass
