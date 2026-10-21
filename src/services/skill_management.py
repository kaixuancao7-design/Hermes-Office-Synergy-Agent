"""Persistent skill versions and change history."""
import json
import sqlite3
from contextlib import contextmanager
from src.types import Skill, SkillVersion, SkillChangeLog
from src.data.database import db
from src.utils import generate_id, get_timestamp


class SkillVersionManager:
    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(db.db_path)
        conn.execute("CREATE TABLE IF NOT EXISTS skill_version_records (skill_id TEXT, version TEXT, data TEXT, PRIMARY KEY(skill_id, version))")
        conn.execute("CREATE TABLE IF NOT EXISTS skill_change_records (id TEXT PRIMARY KEY, skill_id TEXT, data TEXT)")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def save_version(self, skill, user_id, change_type="update"):
        data = skill.model_dump()
        data.pop("updated_at", None)
        data["created_at"] = get_timestamp()
        data.update(id=generate_id(), skill_id=skill.id, created_by=user_id, change_type=change_type)
        version = SkillVersion.model_validate(data)
        with self._connect() as conn:
            conn.execute("INSERT OR IGNORE INTO skill_version_records VALUES (?, ?, ?)",
                         (skill.id, skill.version, version.model_dump_json()))

    def get_versions(self, skill_id):
        with self._connect() as conn:
            return [SkillVersion.model_validate_json(r[0]) for r in conn.execute("SELECT data FROM skill_version_records WHERE skill_id=? ORDER BY rowid", (skill_id,))]

    def get_version(self, skill_id, version):
        return next((item for item in self.get_versions(skill_id) if item.version == version), None)

    def _log_change(self, skill_id, current_version, change_type, description, user_id):
        change = SkillChangeLog(id=generate_id(), skill_id=skill_id, version=current_version,
            changed_by=user_id, changed_at=get_timestamp(), change_type=change_type, change_description=description)
        with self._connect() as conn:
            conn.execute("INSERT INTO skill_change_records VALUES (?, ?, ?)", (change.id, skill_id, change.model_dump_json()))

    def rollback(self, skill_id, target_version, user_id):
        version = self.get_version(skill_id, target_version)
        current = db.get_skill(skill_id)
        if version is None or current is None:
            return None
        values = version.model_dump()
        values.update(id=skill_id, created_by=current.created_by, created_at=current.created_at, updated_at=get_timestamp())
        return Skill.model_validate(values)

    def get_change_logs(self, skill_id):
        with self._connect() as conn:
            return [SkillChangeLog.model_validate_json(r[0]) for r in conn.execute("SELECT data FROM skill_change_records WHERE skill_id=? ORDER BY rowid", (skill_id,))]


skill_version_manager = SkillVersionManager()
