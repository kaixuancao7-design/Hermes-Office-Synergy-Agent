from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.data.database import Database
from src.plugins.skill_managers import DatabaseSkillManager, HybridSkillManager
from src.tools.runtime import current_user


@pytest.mark.parametrize("plugin_class", [DatabaseSkillManager, HybridSkillManager])
def test_skill_plugins_share_persistence_permissions_and_versions(monkeypatch, tmp_path, plugin_class):
    import src.skills.manager as domain
    import src.skills.custom_skills as custom
    database = Database(str(tmp_path / "skills.db"))
    monkeypatch.setattr(domain, "db", database)
    monkeypatch.setattr(custom, "db", database)
    monkeypatch.setattr(domain.skill_manager, "_internal_skills_loaded", False)
    permissions = SimpleNamespace(check_skill_permission=Mock(return_value=SimpleNamespace(allowed=False)))
    monkeypatch.setattr(domain, "permission_service", permissions)
    versions = SimpleNamespace(save_version=Mock(), _log_change=Mock())
    monkeypatch.setattr(domain, "skill_version_manager", versions)
    monkeypatch.setattr(domain, "audit_log_service", SimpleNamespace(log_skill_edit=Mock(), log_skill_delete=Mock()))
    plugin = plugin_class()
    with pytest.raises(PermissionError):
        plugin.create_skill({"name": "sample", "steps": [{"id": "one", "action": "hello", "parameters": {}}]})
    token = current_user.set("alice")
    try:
        skill = plugin.create_skill({"name": "sample", "steps": [{"id": "one", "action": "hello", "parameters": {}}], "trigger_patterns": ["hello"]})
        assert skill.created_by == "alice"
        assert plugin.get_skill(skill.id).trigger_patterns == ["hello"]
        with pytest.raises(PermissionError):
            plugin.update_skill(skill.id, {"name": "blocked"})
        with pytest.raises(PermissionError):
            plugin.delete_skill(skill.id)
        assert database.get_skill(skill.id).name == "sample"
        permissions.check_skill_permission.return_value.allowed = True
        changed = plugin.update_skill(skill.id, {"name": "updated"})
        assert changed.version == "1.0.1"
        assert versions.save_version.call_count == 2
        # A second instance immediately observes the same definition.
        assert plugin_class().get_skill(skill.id).name == "updated"
        assert plugin.delete_skill(skill.id)
        assert database.get_skill(skill.id) is None
        versions._log_change.assert_called()
    finally:
        current_user.reset(token)


def test_tool_schemas_have_one_source_and_compatibility_exports():
    from src.tools.schemas import FileOperationsInput
    from src.engine.langchain_tools import FileOperationsInput as CompatibilityInput
    from src.engine.langchain_tools import get_tool_schemas_openai, get_tool_descriptors_mcp
    from src.tools.base import tool_schema
    from src.plugins.tool_executors import FileOperationsTool
    assert CompatibilityInput is FileOperationsInput is tool_schema(FileOperationsTool)
    openai = get_tool_schemas_openai(["file_operations"])[0]
    mcp = get_tool_descriptors_mcp(["file_operations"])[0]
    assert openai["parameters"] == mcp["inputSchema"]


def test_code_bridge_uses_canonical_tool_id(monkeypatch):
    import json
    from src.engine import langchain_tools as bridge
    execute = Mock(return_value={"success": True})
    monkeypatch.setattr(bridge, "_get_executor", lambda: SimpleNamespace(execute=execute))
    assert json.loads(bridge._execute_code("print(1)"))["success"]
    execute.assert_called_once_with("code_execution", {"code": "print(1)", "language": "python"})
