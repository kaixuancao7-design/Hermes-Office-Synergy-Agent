"""Durable request claims prevent automatic replay of uncertain side effects."""
import hashlib
import json
import sqlite3


class RequestStore:
    def __init__(self, path):
        self.path = path
        with sqlite3.connect(path) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS routing_requests (
                request_key TEXT PRIMARY KEY, fingerprint TEXT NOT NULL,
                status TEXT NOT NULL, response TEXT, stage TEXT)""")

    @staticmethod
    def identity(message):
        metadata = message.metadata or {}
        identity = [metadata.get("source", "internal"), message.user_id,
                    metadata.get("message_id") or message.id]
        key = hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()
        payload = [message.content, message.role, metadata]
        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()
        return key, fingerprint

    def claim(self, key, fingerprint):
        with sqlite3.connect(self.path) as conn:
            inserted = conn.execute("INSERT OR IGNORE INTO routing_requests VALUES (?, ?, 'processing', NULL, 'entry')",
                                    (key, fingerprint)).rowcount
            row = conn.execute("SELECT fingerprint, status, response, stage FROM routing_requests WHERE request_key = ?", (key,)).fetchone()
        if row[0] != fingerprint:
            return "conflict", None
        return ("new", None) if inserted else (row[1], row[2])

    def finish(self, key, response, status="completed", stage="done"):
        with sqlite3.connect(self.path) as conn:
            conn.execute("UPDATE routing_requests SET status=?, response=?, stage=? WHERE request_key=?",
                         (status, response, stage, key))
