"""Durable, account-scoped upload queue. No password or token is stored here."""
from __future__ import annotations

import hashlib
from contextlib import contextmanager
import json
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
import uuid

import requests


class PermanentUploadError(Exception):
    pass


def server_url(value):
    value = value.rstrip('/')
    p = urlsplit(value)
    if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password or p.query or p.fragment or p.path:
        raise ValueError('Server must be an http(s) origin without a path, credentials, query or fragment.')
    return value


@dataclass(frozen=True)
class UploadConfig:
    server: str
    username: str
    password: str = ''
    token: str = ''
    timeout: tuple = (3, 15)

    def __post_init__(self):
        object.__setattr__(self, 'server', server_url(self.server))
        if not self.username or not (self.password or self.token):
            raise ValueError('Supply an account name and either a password or a token.')


class EventQueue:
    """SQLite commits the JPEG reference before network transmission starts."""
    def __init__(self, state_dir, server, username):
        self.server, self.username = server_url(server), username
        namespace = hashlib.sha256((self.server + '\0' + username).encode()).hexdigest()[:16]
        self.root = Path(state_dir).resolve() / namespace
        self.root.mkdir(parents=True, exist_ok=True)
        self.database = self.root / 'queue.sqlite3'
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('''CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY, title TEXT NOT NULL, text TEXT NOT NULL,
                image_path TEXT NOT NULL, image_sha256 TEXT NOT NULL, created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
                next_attempt REAL NOT NULL DEFAULT 0, last_error TEXT NOT NULL DEFAULT '',
                post_id INTEGER, delivered_at TEXT)''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.database, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def enqueue(self, title, text, jpeg, event_id=None):
        event_id = str(uuid.UUID(str(event_id))) if event_id else str(uuid.uuid4())
        image = self.root / (event_id + '.jpg')
        digest = hashlib.sha256(jpeg).hexdigest()
        with self.connect() as db:
            previous = db.execute('SELECT * FROM events WHERE event_id=?', (event_id,)).fetchone()
            if previous:
                if (previous['title'], previous['text'], previous['image_sha256']) != (title, text, digest):
                    raise ValueError('An existing event ID cannot be reused for different content.')
                return event_id
            # A crash between writing the JPEG and committing can leave an orphan
            # JPEG, but never a committed queue entry without its image.
            temporary = image.with_suffix('.jpg.tmp')
            temporary.write_bytes(jpeg)
            temporary.replace(image)
            db.execute('''INSERT INTO events
                (event_id,title,text,image_path,image_sha256,created_at) VALUES (?,?,?,?,?,?)''',
                (event_id, title, text, str(image), digest, datetime.now(timezone.utc).isoformat()))
        return event_id

    def due(self, now=None):
        with self.connect() as db:
            row = db.execute("SELECT * FROM events WHERE status='pending' AND next_attempt<=? ORDER BY created_at LIMIT 1",
                             (time.time() if now is None else now,)).fetchone()
            return dict(row) if row else None

    def delivered(self, event_id, post_id):
        with self.connect() as db:
            db.execute("UPDATE events SET status='sent',post_id=?,delivered_at=?,last_error='' WHERE event_id=?",
                       (post_id, datetime.now(timezone.utc).isoformat(), event_id))

    def failed(self, event_id, reason, permanent=False):
        with self.connect() as db:
            row = db.execute('SELECT attempts FROM events WHERE event_id=?', (event_id,)).fetchone()
            attempts = row['attempts'] + 1
            delay = min(60, 2 ** min(attempts, 6))
            db.execute('UPDATE events SET attempts=?,next_attempt=?,last_error=?,status=? WHERE event_id=?',
                       (attempts, time.time() + delay, reason[:160], 'blocked' if permanent else 'pending', event_id))

    def status(self):
        with self.connect() as db:
            counts = {row['status']: row['n'] for row in db.execute('SELECT status,COUNT(*) AS n FROM events GROUP BY status')}
            rows = [dict(r) for r in db.execute('SELECT event_id,title,status,attempts,last_error,post_id FROM events ORDER BY created_at')]
        return {'server': self.server, 'account': self.username,
                'counts': {s: counts.get(s, 0) for s in ['pending', 'sent', 'blocked']}, 'events': rows}


class ApiUploader:
    def __init__(self, config, session=None):
        self.config = config
        self.session = session or requests.Session()
        self.token = config.token

    def upload(self, event):
        if not self.token:
            response = self.session.post(self.config.server + '/api/token/',
                data={'username': self.config.username, 'password': self.config.password},
                timeout=self.config.timeout, allow_redirects=False)
            if response.status_code in (400, 401, 403):
                raise PermanentUploadError('Login failed; check the configured account.')
            response.raise_for_status()
            self.token = response.json()['token']
        image = Path(event['image_path'])
        if not image.is_file() or hashlib.sha256(image.read_bytes()).hexdigest() != event['image_sha256']:
            raise PermanentUploadError('Queued image is missing or its checksum changed.')
        with image.open('rb') as photo:
            response = self.session.post(self.config.server + '/api_root/Post/',
                data={'title': event['title'], 'text': event['text']},
                files={'image': (image.name, photo, 'image/jpeg')},
                headers={'Authorization': 'Token ' + self.token, 'Accept': 'application/json',
                         'X-Event-ID': event['event_id']},
                timeout=self.config.timeout, allow_redirects=False)
        if response.status_code == 401:
            self.token = ''
            raise PermanentUploadError('Upload authentication failed; check the configured account.')
        if 400 <= response.status_code < 500 and response.status_code not in (408, 429):
            raise PermanentUploadError('Server rejected the event (HTTP %s).' % response.status_code)
        response.raise_for_status()
        if response.status_code not in (200, 201):
            raise PermanentUploadError('Unexpected upload response; do not follow redirects with credentials.')
        if response.headers.get('X-Event-ID') != event['event_id']:
            raise PermanentUploadError('Server did not acknowledge the event ID; deploy the assessment-02 server.')
        post_id = response.json().get('id')
        if not isinstance(post_id, int) or isinstance(post_id, bool):
            raise PermanentUploadError('Server response did not contain a valid post ID.')
        return post_id


class QueueWorker:
    def __init__(self, queue, uploader, background=True):
        self.queue, self.uploader = queue, uploader
        self.stop = threading.Event()
        self.wake = threading.Event()
        self.lock = threading.Lock()
        self.thread = None
        if background:
            self.thread = threading.Thread(target=self._run, name='edge-uploader', daemon=True)
            self.thread.start()

    def process_one(self, now=None):
        with self.lock:
            event = self.queue.due(now)
            if event is None:
                return False
            try:
                post_id = self.uploader.upload(event)
                self.queue.delivered(event['event_id'], post_id)
                print('EDGE uploaded event=%s post=%s' % (event['event_id'], post_id), flush=True)
            except PermanentUploadError as error:
                self.queue.failed(event['event_id'], str(error), permanent=True)
                print('EDGE blocked event=%s: %s' % (event['event_id'], error), flush=True)
            except (requests.RequestException, ValueError, KeyError, OSError) as error:
                # Do not log request headers, URLs containing secrets or login bodies.
                reason = type(error).__name__
                self.queue.failed(event['event_id'], reason)
                print('EDGE queued retry event=%s reason=%s' % (event['event_id'], reason), flush=True)
            return True

    def _run(self):
        while not self.stop.is_set():
            if not self.process_one():
                self.wake.wait(0.5)
                self.wake.clear()

    def close(self, wait_seconds=5):
        # Sent/blocked/pending rows remain durable across process restarts.
        deadline = time.monotonic() + wait_seconds
        while self.thread and time.monotonic() < deadline and self.queue.status()['counts']['pending']:
            self.wake.set()
            time.sleep(0.1)
        self.stop.set()
        self.wake.set()
        if self.thread:
            self.thread.join(timeout=self.uploader.config.timeout[0] + self.uploader.config.timeout[1] + 1)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Inspect the local Edge delivery queue without printing credentials.')
    parser.add_argument('--state-dir', type=Path, required=True)
    parser.add_argument('--server', required=True)
    parser.add_argument('--username', required=True)
    args = parser.parse_args()
    print(json.dumps(EventQueue(args.state_dir, args.server, args.username).status(), ensure_ascii=False, indent=2))
