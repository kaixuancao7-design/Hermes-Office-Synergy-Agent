"""Integration regressions using real tool classes and shipped preset definitions."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from src.types import Skill, SkillStep
from src.data.database import db
from src.engine.skill_executor import SkillStepExecutor
from src.tools.base import BaseTool, ToolSchema
from pydantic import Field


@pytest.fixture
def executor(monkeypatch):
    from src.plugins.tool_executors import BasicToolExecutor, SandboxedToolExecutor
    for cls in (BasicToolExecutor, SandboxedToolExecutor):
        monkeypatch.setattr(cls, "_initialize_feishu_client", lambda self: None)
        monkeypatch.setattr(cls, "_initialize_memory_store", lambda self: None)
    db.set_user_role("contract-user", "user")
    db.set_user_role("contract-admin", "admin")
    return SandboxedToolExecutor()


def make_skill(steps, **extra):
    return Skill(id="contract-skill", name="Contract", description="Contract test", type="custom",
        trigger_patterns=[], steps=steps, metadata={}, created_at=1, updated_at=1, created_by="contract-user", **extra)


def test_registration_and_real_ppt_preset(executor, monkeypatch):
    from src.skills.preset_skills import preset_skills_manager
    from src.plugins.tool_executors import BasicToolExecutor
    from src.plugins import model_routers
    from src.engine import skill_executor as engine
    basic = BasicToolExecutor()
    assert {"document_search", "memory_search", "web_search", "code_execution", "file_operations",
            "feishu_file_read", "generate_ppt", "generate_ppt_from_content", "read_file"} <= set(basic.get_tools())
    for cls in executor.tools.values():
        cls(executor=executor)
    model = AsyncMock(side_effect=[json.dumps([{"title": "Intro", "content": ["Verified data"]}]),
                                   json.dumps([{"type": "content", "title": "Intro", "content": "Verified data"}])])
    monkeypatch.setattr(model_routers, "call_model", model)
    monkeypatch.setattr(engine, "call_model", AsyncMock(return_value="Completed"))
    definition = next(s for s in preset_skills_manager._get_default_skills() if s["id"] == "ppt-generate")
    skill = Skill(**definition, type="preset", created_at=1, updated_at=1, created_by="system")
    runner = SkillStepExecutor(); runner._tool_executor = executor
    result = asyncio.run(runner.execute_skill(skill, "Prepare a report about verified data", "contract-user"))
    assert result.steps_failed == 0, result.step_results
    assert result.steps_executed == 5
    artifact = result.step_results[3]["result"]["file_path"]
    assert Path(artifact).is_file()
    assert result.step_results[4]["result"]["metrics"]["slides_count"] == 2
    assert model.call_count == 2


def test_markdown_lossless_roundtrip_and_legacy_types(tmp_path):
    from src.skills.skill_md import SkillMarkdownManager
    manager = SkillMarkdownManager(str(tmp_path))
    skill = make_skill([SkillStep(id="first", action="summarize", description="First step",
        parameters={"instruction": "line one\nline two", "items": [1, {"x": True}], "limit": 3}, next_step_id="last"),
        SkillStep(id="last", action="summarize", parameters={}, condition="first.success")])
    skill.metadata = {"references": ["docs/reference.md"], "nested": {"flag": False}}
    assert manager.markdown_to_skill(manager.skill_to_markdown(skill)).model_dump() == skill.model_dump()
    legacy = "---\nname: Legacy\ntype: learned\ntriggers:\n  - legacy\n---\n### Step 1: action\n- **Action**: summarize\n- **Parameters**:\n  - `limit`: 3\n  - `items`: [1, 2]\n  - `instruction`: first\nsecond\n"
    parsed = manager.markdown_to_skill(legacy)
    assert parsed.steps[0].parameters == {"limit": 3, "items": [1, 2], "instruction": "first\nsecond"}
    assert parsed.id == manager.markdown_to_skill(legacy).id


def test_failure_is_not_success_and_stops_dependents(executor, monkeypatch):
    from src.engine import skill_executor as engine
    monkeypatch.setattr(engine, "call_model", AsyncMock(return_value="summary"))
    class Failed(BaseTool):
        def execute(self, params): return {"success": False, "error": "controlled error"}
    executor.tools["failed"] = Failed
    runner = SkillStepExecutor(); runner._tool_executor = executor
    skill = make_skill([SkillStep(id="first", action="failed", type="tool", parameters={}),
                        SkillStep(id="second", action="summarize", parameters={})])
    result = asyncio.run(runner.execute_skill(skill, "query", "contract-user"))
    assert result.steps_executed == 0 and result.steps_failed == 1
    assert len(result.step_results) == 1
    assert result.trace.tool_sequence[0].success is False


def test_jump_condition_binding_and_identity(executor, monkeypatch):
    from src.engine import skill_executor as engine
    monkeypatch.setattr(engine, "call_model", AsyncMock(return_value="summary"))
    received = []
    class EchoSchema(ToolSchema):
        value: list = Field()
    class Source(BaseTool):
        def execute(self, params): return {"success": True, "items": [1, 2]}
    class Echo(BaseTool):
        schema = EchoSchema
        def execute(self, params):
            received.append(params)
            return {"success": True, "result": params["value"]}
    executor.tools.update(source=Source, echo=Echo)
    skill = make_skill([SkillStep(id="first", action="source", type="tool", parameters={}, next_step_id="last"),
        SkillStep(id="skipped", action="missing", type="tool", parameters={}),
        SkillStep(id="last", action="echo", type="tool", condition="first.success", parameters={"value": "${first.items}", "user_id": "contract-admin"})])
    runner = SkillStepExecutor(); runner._tool_executor = executor
    result = asyncio.run(runner.execute_skill(skill, "query", "contract-user"))
    assert result.steps_failed == 0 and result.steps_executed == 2
    assert received[0]["value"] == [1, 2]
    assert received[0]["user_id"] == "contract-user"
    skill.steps[-1].condition = "false"
    result = asyncio.run(runner.execute_skill(skill, "query", "contract-user"))
    assert result.steps_executed == 1
    assert result.step_results[-1]["skipped"]


def test_paths_and_references_cannot_escape(executor, tmp_path, monkeypatch):
    from src.tools.runtime import parse_paths
    executor.allowed_paths = parse_paths("./workspace")
    assert not executor._is_path_allowed(".env")
    assert not executor._is_path_allowed("workspace-private/file.txt")
    assert executor._is_path_allowed("workspace/input.txt")
    assert len(parse_paths('["./workspace", "./output"]')) == 2
    secret = tmp_path / "secret.txt"; secret.write_text("synthetic secret")
    runner = SkillStepExecutor()
    skill = make_skill([]); skill.metadata = {"references": [str(secret)]}
    assert runner._load_reference_docs(skill) == {}


def test_tool_permissions_and_container_fail_closed(executor, monkeypatch):
    from src.tools import code_sandbox
    assert executor.execute("code_execution", {"user_id": "contract-user", "code": "print(1)"})["success"] is False
    monkeypatch.setattr(code_sandbox.shutil, "which", lambda binary: None)
    result = executor.execute("code_execution", {"user_id": "contract-admin", "code": "print(1)"})
    assert result["success"] is False and "Docker" in result["error"]
    assert not code_sandbox.execute_python({"code": ""})["success"]


def test_dynamic_code_params_are_generated_and_checked(executor, monkeypatch):
    from src.engine import skill_executor as engine
    from src.tools import code_sandbox
    model = AsyncMock(side_effect=[json.dumps({"code": "print(42)", "user_id": "other"}), "Done"])
    monkeypatch.setattr(engine, "call_model", model)
    received = []
    monkeypatch.setattr(code_sandbox, "execute_python", lambda params, timeout: received.append(params) or {"success": True, "result": {"stdout": "42"}})
    skill = make_skill([SkillStep(id="code", action="code_execution", type="tool", parameters={"instruction": "Compute the answer"})])
    runner = SkillStepExecutor(); runner._tool_executor = executor
    result = asyncio.run(runner.execute_skill(skill, "Compute", "contract-admin"))
    assert result.steps_failed == 0
    assert received[0]["code"] == "print(42)" and received[0]["user_id"] == "contract-admin"


def test_update_versions_and_permissions_api_storage(executor):
    from src.skills.manager import SkillManager
    from src.services.skill_management import skill_version_manager
    manager = SkillManager(); manager._internal_skills_loaded = True
    skill = make_skill([SkillStep(id="one", action="summarize", parameters={})]); db.save_skill(skill)
    with pytest.raises(PermissionError):
        manager.update_skill("contract-user", skill.id, {"name": "Updated"})
    updated = manager.update_skill("contract-admin", skill.id, {"name": "Updated"})
    assert updated.version == "1.0.1"
    assert len(skill_version_manager.get_versions(skill.id)) == 2
    rolled = manager.rollback_to_version("contract-admin", skill.id, "1.0.0")
    assert rolled.name == "Contract"
    assert skill_version_manager.get_change_logs(skill.id)
    db.grant_permission("contract-permission", "skill", skill.id, "contract-user", "execute", "contract-admin")
    assert db.get_resource_permissions("skill", skill.id)[0]["permission"] == "execute"


def test_fallback_and_loop_limit(executor, monkeypatch):
    from src.engine import skill_executor as engine
    monkeypatch.setattr(engine, "call_model", AsyncMock(return_value="summary"))
    class Failure(BaseTool):
        def execute(self, params): return {"success": False, "error": "unavailable"}
    class Success(BaseTool):
        def execute(self, params): return {"success": True, "result": "fallback result"}
    executor.tools.update(fail=Failure, recover=Success)
    runner = SkillStepExecutor(); runner._tool_executor = executor
    skill = make_skill([SkillStep(id="one", action="fail", type="tool", parameters={"fallback_tool": "recover"})])
    result = asyncio.run(runner.execute_skill(skill, "query", "contract-user"))
    assert result.steps_executed == 1 and result.steps_failed == 0
    skill.steps[0].action = "recover"; skill.steps[0].next_step_id = "one"
    runner.MAX_STEPS = 2
    result = asyncio.run(runner.execute_skill(skill, "query", "contract-user"))
    assert result.steps_executed == 2 and result.steps_failed == 1
    assert "limit" in result.step_results[-1]["error"]


def test_private_skill_denied_and_missing_parameters_fail(executor, monkeypatch):
    from src.engine import skill_executor as engine
    monkeypatch.setattr(engine, "call_model", AsyncMock(return_value="not JSON"))
    runner = SkillStepExecutor(); runner._tool_executor = executor
    skill = make_skill([SkillStep(id="one", action="file_operations", type="tool", parameters={"operation": "read"})])
    with pytest.raises(PermissionError):
        asyncio.run(runner.execute_skill(skill, "query", "unknown-guest"))
    result = asyncio.run(runner.execute_skill(skill, "query", "contract-user"))
    assert result.steps_failed == 1 and result.steps_executed == 0


def test_container_command_is_restricted_and_nonzero_exit_fails(monkeypatch):
    from src.tools import code_sandbox
    commands = []
    monkeypatch.setattr(code_sandbox.shutil, "which", lambda name: "docker")
    def run(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=1 if command[1] == "run" else 0, stdout="", stderr="controlled container failure")
    monkeypatch.setattr(code_sandbox.subprocess, "run", run)
    result = code_sandbox.execute_python({"code": "print(1)"})
    assert not result["success"]
    assert {"--network=none", "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges",
            "--pids-limit=64", "--memory=256m", "--cpus=1", "--pull=never"} <= set(commands[0])
    assert commands[-1][1:3] == ["rm", "-f"]


def test_content_tool_async_bridge(executor, monkeypatch):
    from src.plugins import model_routers
    monkeypatch.setattr(model_routers, "call_model", AsyncMock(return_value=json.dumps([
        {"title": "Introduction", "content": ["Verified content"]}])))
    result = executor.execute("generate_ppt_from_content", {"user_id": "contract-user", "content": "Verified content", "title": "Report"})
    assert result["success"], result
    assert ".pptx" in result["result"]
    monkeypatch.setattr(model_routers, "call_model", AsyncMock(side_effect=RuntimeError("model unavailable")))
    result = executor.execute("generate_outline", {"user_id": "contract-user", "content": "Source"})
    assert not result["success"]


def test_every_preset_has_valid_step_graph_and_registered_tools(executor):
    from src.skills.preset_skills import preset_skills_manager
    runner = SkillStepExecutor(); runner._tool_executor = executor
    presets = preset_skills_manager._get_default_skills()
    assert len(presets) == 12
    for definition in presets:
        skill = Skill(**definition, type="preset", created_at=1, updated_at=1)
        ids = {step.id for step in skill.steps}
        assert len(ids) == len(skill.steps)
        for step in skill.steps:
            assert step.description
            assert step.next_step_id is None or step.next_step_id in ids
            if runner._is_tool_action(step.action):
                assert step.action in executor.tools
            if step.action == "code_execution":
                assert "df" not in step.parameters.get("code", "")


def test_unapproved_draft_cannot_be_published(monkeypatch):
    from src.skills.learned_skills import LearnedSkillsManager
    manager = LearnedSkillsManager()
    monkeypatch.setattr(manager, "_get_draft", lambda key: {"status": "rejected", "skill_name": "Rejected"})
    assert manager.create_from_draft("contract-admin", "draft") is None


def test_mcp_sensitive_tools_require_verified_identity():
    import ast
    from src.tools.runtime import current_user
    source = Path(__file__).resolve().parents[1] / "src/engine/mcp_server.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    helper = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "_execute_guarded")
    ns = {}
    exec(compile(ast.Module(body=[helper], type_ignores=[]), str(source), "exec"), ns)
    token = current_user.set(None)
    try:
        result = asyncio.run(ns["_execute_guarded"]("code_execution", {"user_id": "contract-admin", "code": "print(1)"}))
        assert not result["success"] and "authenticated" in result["error"]
    finally:
        current_user.reset(token)
