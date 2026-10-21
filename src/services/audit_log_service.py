"""Persistent audit log with a SHA-256 chain and bounded export paths."""
import hashlib
import json
import sqlite3
import threading
from pathlib import Path
from src.config import settings
from src.types import AuditLog, AuditQueryResult
from src.utils import generate_id, get_timestamp


class AuditLogService:
    def __init__(self, db_path=None):
        self.db_path = db_path or settings.DATABASE_PATH
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS audit_entries (seq INTEGER PRIMARY KEY AUTOINCREMENT, payload TEXT NOT NULL)")

    @staticmethod
    def _checksum(data):
        return hashlib.sha256(json.dumps({k: v for k, v in data.items() if k != "checksum"}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    def _all(self):
        with sqlite3.connect(self.db_path) as conn:
            return [AuditLog(**json.loads(row[0])) for row in conn.execute("SELECT payload FROM audit_entries ORDER BY seq")]

    def _record(self, operator, action, target_type, target_id, detail, result="success"):
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT payload FROM audit_entries ORDER BY seq DESC LIMIT 1").fetchone()
            data = AuditLog(id=generate_id(), operation_type=action, operator_id=operator,
                target_type=target_type, target_id=target_id, operation_detail=str(detail),
                result=result, timestamp=get_timestamp(), checksum="",
                previous_checksum=json.loads(row[0])["checksum"] if row else "").model_dump()
            data["checksum"] = self._checksum(data)
            conn.execute("INSERT INTO audit_entries(payload) VALUES (?)", (json.dumps(data, ensure_ascii=False),))

    def log_action(self, user_id, action, resource, details=None):
        self._record(user_id, action, "resource", resource, json.dumps(details or {}, ensure_ascii=False))

    def log_error(self, user_id, action, resource, error):
        self._record(user_id, action, "resource", resource, error, "failed")

    def log_skill_delete(self, user, skill, name):
        self._record(user, "skill_delete", "skill", skill, name)

    def log_skill_edit(self, user, skill, name, detail):
        self._record(user, "skill_edit", "skill", skill, detail)

    def log_skill_execute(self, user, skill, name):
        self._record(user, "skill_execute", "skill", skill, name)

    def log_role_change(self, user, target, old, new):
        self._record(user, "role_change", "user", target, f"{old} -> {new}")

    def log_permission_grant(self, user, kind, target, recipient, permission):
        self._record(user, "permission_grant", kind, target, f"{recipient}: {permission}")

    def log_permission_revoke(self, user, kind, target, recipient, permission):
        self._record(user, "permission_revoke", kind, target, f"{recipient}: {permission}")

    def query_logs(self, operator_id=None, operation_type=None, target_type=None, target_id=None,
                   start_time=None, end_time=None, result=None, page=1, page_size=20):
        if page < 1 or not 1 <= page_size <= 1000:
            raise ValueError("Invalid pagination")
        logs = self._all()
        filters = dict(operator_id=operator_id, operation_type=operation_type,
                       target_type=target_type, target_id=target_id, result=result)
        logs = [x for x in reversed(logs) if all(v is None or getattr(x, k) == v for k, v in filters.items())
                and (start_time is None or x.timestamp >= start_time)
                and (end_time is None or x.timestamp <= end_time)]
        offset = (page - 1) * page_size
        return AuditQueryResult(logs=logs[offset:offset+page_size], total=len(logs), page=page, page_size=page_size)

    def get_log_by_id(self, log_id):
        return next((x for x in self._all() if x.id == log_id), None)

    def get_operator_logs(self, operator_id):
        return [x for x in self._all() if x.operator_id == operator_id]

    def get_logs_by_type(self, operation_type):
        return [x for x in self._all() if x.operation_type == operation_type]

    def get_user_logs(self, user_id, limit=20):
        return list(reversed(self.get_operator_logs(user_id)))[:limit]

    def get_resource_logs(self, resource, limit=20):
        return [x for x in reversed(self._all()) if x.target_id == resource][:limit]

    def verify_log_integrity(self):
        previous = ""
        try:
            for log in self._all():
                data = log.model_dump()
                if log.previous_checksum != previous or log.checksum != self._checksum(data):
                    return False
                previous = log.checksum
            return True
        except (ValueError, TypeError, KeyError):
            return False

    def export_logs(self, file_path):
        try:
            destination = Path(file_path).resolve()
            destination.relative_to(Path("output").resolve())
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(json.dumps([x.model_dump() for x in self._all()], ensure_ascii=False, indent=2), encoding="utf-8")
            return True
        except (ValueError, OSError):
            return False


audit_log_service = AuditLogService()
