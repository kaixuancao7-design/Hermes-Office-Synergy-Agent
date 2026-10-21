import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]


def test_domain_router_split_preserves_public_routes():
    from fastapi import FastAPI
    from src.api.v1.endpoints import router
    app = FastAPI()
    app.include_router(router)
    actual = sorted([method, path] for path, item in app.openapi()["paths"].items()
                    for method in (verb.upper() for verb in item if verb in {"get", "post", "put", "delete", "patch"}))
    expected = json.loads((ROOT / "tests/api_routes_snapshot.json").read_text())
    assert actual == expected


def test_application_import_has_no_database_network_or_file_side_effects(tmp_path):
    code = '''
import sqlite3, socket
def forbidden(*args, **kwargs):
    raise AssertionError("Import attempted external resource initialization")
sqlite3.connect = forbidden
socket.create_connection = forbidden
import src.main
from src.data.database import db
from src.gateway.message_router import message_router
from src.engine.ppt_workflow import ppt_workflow
assert not db._initialized
assert not message_router._sessions_loaded
assert not ppt_workflow._graph_initialized
'''
    env = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1",
           "DATABASE_PATH": str(tmp_path / "data/agent.db"), "LOG_DIR": str(tmp_path / "logs")}
    result = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert list(tmp_path.iterdir()) == []


def test_recent_file_context_is_scoped_to_user(monkeypatch):
    from src.services.file_context import FileContextService
    from src.data.vector_store import rag_manager
    query = Mock(return_value=[])
    monkeypatch.setattr(rag_manager, "query", query)
    database = Mock()
    database.get_recent_messages.return_value = []
    assert FileContextService(database, lambda: None)._get_recent_file_content("alice") == ""
    query.assert_called_once_with("__recent_upload__", k=3, user_id="alice")
