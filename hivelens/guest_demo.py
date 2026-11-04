"""One fixed public-photo demo, with a persistent lifetime quota and global cooldown.

The server runs one process/replica. The SQLite reservation survives restarts;
failed attempts consume quota too. No uploaded data or user prompt is accepted.
"""
from contextlib import contextmanager
import math
import sqlite3
import threading
import time

from . import config

INTERVAL = 15 * 60
_lock = threading.Lock()
_active_job = None

SOURCE = {
    "title": "Frame from hive of honey bee (apis mellifera)",
    "author": "John Pons",
    "url": "https://commons.wikimedia.org/wiki/File:Frame_from_hive_of_honey_bee_(apis_mellifera).jpg",
    "license": "CC BY-SA 4.0",
    "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
    "changes": "JPEG re-encoding, resized to at most 1024 pixels, analysis annotations; derived images retain CC BY-SA 4.0.",
}


class Unavailable(Exception):
    pass


def enabled():
    return config.PUBLIC_READ and config.has_api_key() and config.GUEST_DEMO_LIMIT > 0


@contextmanager
def _db():
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DATA_DIR / 'guest-demo.sqlite3', timeout=5, isolation_level=None)
    try:
        conn.execute('CREATE TABLE IF NOT EXISTS quota (id INTEGER PRIMARY KEY, used INTEGER NOT NULL, last_start REAL NOT NULL)')
        conn.execute('INSERT OR IGNORE INTO quota VALUES (1, 0, 0)')
        yield conn
    finally:
        conn.close()


def status():
    if not enabled():
        return {"enabled": False}
    with _lock, _db() as conn:
        used, last = conn.execute('SELECT used, last_start FROM quota WHERE id=1').fetchone()
        return {"enabled": True, "limit": config.GUEST_DEMO_LIMIT,
                "remaining": max(0, config.GUEST_DEMO_LIMIT - used),
                "retry_after": max(0, math.ceil(last + INTERVAL - time.time())),
                "running": _active_job is not None, "interval_seconds": INTERVAL}


def reserve(job_id):
    global _active_job
    if not enabled():
        raise Unavailable('The live sample is not enabled. Explore a saved analysis instead.')
    with _lock, _db() as conn:
        conn.execute('BEGIN IMMEDIATE')
        used, last = conn.execute('SELECT used, last_start FROM quota WHERE id=1').fetchone()
        now = time.time()
        if used >= config.GUEST_DEMO_LIMIT:
            raise Unavailable('The shared live-demo quota has been used. Saved analyses remain available.')
        if _active_job is not None:
            raise Unavailable('A sample analysis is already running. Please explore a saved analysis meanwhile.')
        if now < last + INTERVAL:
            raise Unavailable(f'The shared sample can run again in {math.ceil((last + INTERVAL - now) / 60)} minutes.')
        conn.execute('UPDATE quota SET used=used+1, last_start=? WHERE id=1', (now,))
        conn.execute('COMMIT')
        _active_job = job_id


def finish(job_id):
    global _active_job
    with _lock:
        if _active_job == job_id:
            _active_job = None
