"""Learning lifecycle regressions using isolated SQLite databases and fake models."""
import asyncio
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from src.data.database import db, Database
from src.types import Skill, SkillStep, SkillDraft, ExecutionTrace, ToolCallRecord
from src.utils import get_timestamp


@pytest.fixture
def learning_db(tmp_path, monkeypatch):
    path = tmp_path / "learning.db"
    isolated = Database(str(path))
    monkeypatch.setattr(db, "db_path", str(path))
    from src.skills.skill_md import skill_md_manager
    directory = tmp_path / "learned"
    directory.mkdir()
    monkeypatch.setattr(skill_md_manager, "base_dir", str(directory))
    isolated.set_user_role("review-admin", "admin")
    isolated.set_user_role("alice", "user")
    isolated.set_user_role("bob", "user")
    return isolated


def trace(success=True, user="alice", trace_id="source"):
    return ExecutionTrace(trace_id=trace_id, user_id=user, query="reusable workflow", final_response="Result",
        step_count=5, created_at=get_timestamp(), tool_sequence=[ToolCallRecord(tool_id="web_search",
            parameters={}, result="result", success=success, step_index=i) for i in range(5)])


def draft(draft_id="draft", user="alice"):
    return SkillDraft(id=draft_id, skill_name="Reviewed workflow", description="A reusable workflow",
        trigger_patterns=["reviewed", "workflow"], steps=[SkillStep(id="first", action="summarize", type="llm",
            description="Summary", parameters={"instruction": "Summarize the actual input"})],
        original_context="context", original_output="before", corrected_output="after", user_intent="test",
        user_id=user, created_at=get_timestamp(), status="pending_review")


def skill(skill_id="learned", user="alice", created_at=None):
    return Skill(id=skill_id, name="Reviewed workflow", description="A reusable workflow", type="learned",
        trigger_patterns=["reviewed", "workflow"], steps=draft().steps, metadata={}, version="1.2.3",
        created_by=user, created_at=get_timestamp() if created_at is None else created_at, updated_at=get_timestamp())


def test_generation_rejects_failures_deduplicates_and_never_exports(learning_db, monkeypatch):
    from src.engine import skill_generator as module
    from src.skills.skill_md import skill_md_manager
    model = AsyncMock(return_value=json.dumps({"skill_name": "Generated workflow", "description": "Reuse workflow",
        "trigger_patterns": ["generated", "workflow"], "steps": [{"action": "summarize", "type": "llm",
            "parameters": {"instruction": "Summarize input"}}], "confidence": .9}))
    monkeypatch.setattr(module, "call_model", model)
    generator = module.SkillAutoGenerator()
    assert not generator.should_trigger(trace(False))
    assert asyncio.run(generator.generate_from_trace(trace(False))) is None
    assert model.call_count == 0
    async def run():
        first, second = await asyncio.gather(generator.generate_from_trace(trace()), generator.generate_from_trace(trace()))
        assert first == second
        assert len(db.get_skill_drafts_by_user("alice")) == 1
        assert db.get_skill_draft(first)["status"] == "pending_review"
        return first
    first = asyncio.run(run())
    calls = model.call_count
    assert asyncio.run(generator.generate_from_trace(trace())) == first
    assert model.call_count == calls
    assert not db.get_all_skills()
    assert not skill_md_manager.list_skill_files()
    from src.engine.learning_cycle import LearningCycle
    LearningCycle().manual_review_skill(first, True, "review-admin")
    published = db.get_published_skill_id(first)
    reopened = Database(db.db_path)
    assert not reopened.get_skill(published).metadata.get("quarantined")
    assert any(item.id == published for item in reopened.get_skills_summaries())


def test_publication_requires_review_and_is_atomic_and_idempotent(learning_db):
    from src.engine.learning_cycle import LearningCycle
    from src.skills.skill_md import skill_md_manager
    from src.services.skill_management import skill_version_manager
    candidate = draft(); db.save_skill_draft(candidate.model_dump())
    cycle = LearningCycle()
    with pytest.raises(PermissionError):
        cycle.manual_review_skill(candidate.id, True, "bob")
    assert not db.get_all_skills()
    result = cycle.manual_review_skill(candidate.id, True, "review-admin")
    assert result.status == "approved"
    published = db.get_published_skill_id(candidate.id)
    assert published
    deployed = db.get_skill(published)
    assert deployed.created_by == "alice" and deployed.version == "1.0.0"
    cycle.manual_review_skill(candidate.id, True, "review-admin")
    assert len(db.get_all_skills()) == 1
    assert len(skill_version_manager.get_versions(published)) == 1
    assert len(skill_md_manager.sync_from_directory()) == 1
    with pytest.raises(ValueError):
        cycle.manual_review_skill(candidate.id, False, "review-admin")
    assert db.get_skill_draft(candidate.id)["status"] == "approved"
    invalid = draft("invalid"); invalid.steps = []
    db.save_skill_draft(invalid.model_dump())
    with pytest.raises(ValueError):
        cycle.manual_review_skill(invalid.id, True, "review-admin")
    assert db.get_skill_draft(invalid.id)["status"] == "pending_review"
    assert db.get_published_skill_id(invalid.id) is None


def test_startup_quarantines_unreviewed_or_modified_files(learning_db):
    from src.skills.skill_md import skill_md_manager
    from src.engine.learning_cycle import LearningCycle
    rogue = skill("rogue")
    rogue.metadata = {"source": "auto_generated"}
    skill_md_manager.write_skill_md(rogue)
    assert skill_md_manager.sync_from_directory() == []
    assert db.get_skill(rogue.id) is None
    candidate = draft(); db.save_skill_draft(candidate.model_dump())
    LearningCycle().manual_review_skill(candidate.id, True, "review-admin")
    published = db.get_skill(db.get_published_skill_id(candidate.id))
    assert len(skill_md_manager.sync_from_directory()) == 1
    published.steps[0].parameters["instruction"] = "Tampered content"
    skill_md_manager.write_skill_md(published)
    assert skill_md_manager.sync_from_directory() == []
    assert db.get_skill(published.id).steps[0].parameters["instruction"] != "Tampered content"


def test_patch_is_owner_scoped_proposal_preserves_graph_and_checks_versions(learning_db):
    from src.engine.skill_patcher import SkillAutoPatcher
    from src.engine.learning_cycle import LearningCycle
    from src.services.skill_management import skill_version_manager
    original = skill()
    original.steps.append(SkillStep(id="last", action="summarize", parameters={"instruction": "Finish"}, condition="first.success"))
    original.steps[0].next_step_id = "last"
    db.save_skill(original)
    patcher = SkillAutoPatcher()
    update = {"updated_steps": [{"parameters": {"instruction": "Improved summary"}}, {"parameters": {"instruction": "Improved final"}}]}
    assert asyncio.run(patcher.find_related_skill("reviewed workflow", "bob")) is None
    assert patcher._apply_patch(original, update, "bob") is None
    proposal = patcher._apply_patch(original, update, "alice")
    assert proposal
    assert db.get_skill(original.id).steps == original.steps
    stored = db.get_skill_draft(proposal)
    assert stored["steps"][0]["id"] == "first" and stored["steps"][0]["next_step_id"] == "last"
    assert stored["steps"][1]["condition"] == "first.success"
    LearningCycle().manual_review_skill(proposal, True, "review-admin")
    updated = db.get_skill(original.id)
    assert updated.version == "1.2.4" and updated.created_by == "alice"
    assert updated.steps[0].parameters["instruction"] == "Improved summary"
    assert len(skill_version_manager.get_versions(original.id)) == 2
    stale = patcher._apply_patch(updated, {"updated_steps": [{"parameters": {"instruction": "Next change"}}, {"parameters": {"instruction": "Finish next"}}]}, "alice")
    updated.version = "1.2.5"; db.save_skill(updated)
    with pytest.raises(ValueError):
        LearningCycle().manual_review_skill(stale, True, "review-admin")
    assert db.get_skill_draft(stale)["status"] == "pending_review"
    assert db.get_skill(original.id).version == "1.2.5"


def test_legacy_database_migration_preserves_rows_and_new_identity(tmp_path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE skills (id TEXT PRIMARY KEY, name TEXT, description TEXT, type TEXT, trigger_patterns TEXT, steps TEXT, metadata TEXT, created_at INTEGER, updated_at INTEGER)")
        conn.execute("INSERT INTO skills VALUES ('old', 'Old', 'Legacy', 'custom', '[]', '[]', '{}', 1, 2)")
    migrated = Database(str(path))
    assert migrated.get_skill("old").name == "Old"
    original = skill(); migrated.save_skill(original)
    reopened = Database(str(path)).get_skill(original.id)
    assert reopened.version == "1.2.3" and reopened.created_by == "alice"
    assert migrated.get_skills_summaries()[-1].version == "1.2.3"


def test_matching_never_counts_usage_and_execution_records_real_outcome(learning_db, monkeypatch):
    from src.skills.triggers import TriggerMatcher
    from src.engine import skill_executor as module
    original = skill(); db.save_skill(original)
    matcher = TriggerMatcher()
    assert matcher.find_relevant_skill("reviewed workflow", "alice")
    assert matcher.find_relevant_skill_with_near_misses("reviewed workflow", "alice")[0]
    assert db.get_skill_usage_stats(original.id)["total_uses"] == 0
    runner = module.SkillStepExecutor()
    monkeypatch.setattr(module, "call_model", AsyncMock(return_value="Result"))
    result = asyncio.run(runner.execute_skill(original, "query", "alice"))
    assert result.steps_failed == 0
    stats = db.get_skill_usage_stats(original.id)
    assert stats["total_uses"] == 1 and stats["success_count"] == 1
    monkeypatch.setattr(runner, "_execute_llm_step", AsyncMock(side_effect=RuntimeError("failure")))
    result = asyncio.run(runner.execute_skill(original, "query", "alice"))
    assert result.steps_failed == 1
    stats = db.get_skill_usage_stats(original.id)
    assert stats["total_uses"] == 2 and stats["success_rate"] == 50


def test_curator_uses_creation_age_and_archived_skills_are_disabled(learning_db):
    from src.engine.skill_curator import SkillCurator
    from src.skills.triggers import TriggerMatcher
    from src.engine.skill_executor import SkillStepExecutor
    new, old = skill("new"), skill("old", created_at=get_timestamp()-40*86400)
    db.save_skill(new); db.save_skill(old)
    curator = SkillCurator(); scored = curator._score_skills()
    assert next(s for s in scored if s["skill_id"] == "new")["days_since_last_use"] < 1
    assert curator._archive_unused(scored) == [old.name]
    assert not db.get_skill("new").metadata.get("archived")
    archived = db.get_skill("old")
    assert archived.metadata["archived"]
    assert all(s.id != "old" for s in db.get_skills_summaries())
    assert TriggerMatcher().load_full_skill("old") is None
    with pytest.raises(PermissionError):
        asyncio.run(SkillStepExecutor().execute_skill(archived, "query", "alice"))


def test_correction_examples_reach_prompt_and_repeated_feedback_deduplicates(learning_db, monkeypatch):
    from src.engine.learning_cycle import LearningCycle
    from src.engine import skill_executor as module
    cycle = LearningCycle()
    first = cycle.capture_correction("alice", "old", "UNIQUE_CORRECTED_PATTERN", "reviewed workflow context")
    assert first
    assert cycle.capture_correction("alice", "old", "UNIQUE_CORRECTED_PATTERN", "reviewed workflow context") == first
    proposed = db.get_skill_draft(first)
    step = SkillStep.model_validate(proposed["steps"][1])
    model = AsyncMock(return_value="Result"); monkeypatch.setattr(module, "call_model", model)
    asyncio.run(module.SkillStepExecutor()._execute_llm_step(step, "neutral", "neutral"))
    assert "UNIQUE_CORRECTED_PATTERN" in model.call_args.args[0]


def test_verification_and_listing_are_real_and_nonexecuting(learning_db):
    from src.services.skill_verification import SkillVerificationService
    service = SkillVerificationService()
    db.save_skill_draft(draft().model_dump()); db.save_skill_draft(draft("other", "bob").model_dump())
    assert service.verify_skill_draft("draft").verified
    assert not service.verify_skill_draft("missing").verified
    assert [d.id for d in service.list_drafts("alice", "pending_review")] == ["draft"]
    invalid = draft("invalid"); invalid.steps[0].next_step_id = "missing"
    db.save_skill_draft(invalid.model_dump())
    assert not service.verify_skill_draft("invalid").verified


def test_concurrent_requests_have_independent_trace_snapshots(learning_db, monkeypatch):
    from src.engine import react_engine as module
    engine = module.ReActEngine()
    monkeypatch.setattr(module, "get_tool_executor", lambda: SimpleNamespace(get_tools=lambda: ["web_search"]))
    async def fake_graph(query, tools, user_id):
        engine._trace_tool_sequence.append(ToolCallRecord(tool_id="web_search", parameters={"owner": user_id}, result=query, success=True, step_index=1))
        await asyncio.sleep(.001)
        return query
    monkeypatch.setattr(engine, "_run_with_langgraph", fake_graph)
    async def run():
        results = await asyncio.gather(engine.run_with_trace("alice", "Alice query", {"message_id": "alice-trace"}),
                                       engine.run_with_trace("bob", "Bob query", {"message_id": "bob-trace"}))
        for user, (response, captured) in zip(("alice", "bob"), results):
            assert captured.user_id == user
            assert captured.tool_sequence[0].parameters["owner"] == user
            assert len(captured.tool_sequence) == 1
            assert db.get_execution_trace(captured.trace_id)["user_id"] == user
    asyncio.run(run())


def test_langgraph_failed_tool_messages_cannot_be_learned():
    from src.engine.react_engine import ReActEngine
    engine = ReActEngine()
    ai = SimpleNamespace(type="ai", tool_calls=[{"id": "call", "name": "web_search", "args": {}}])
    tool = SimpleNamespace(type="tool", tool_call_id="call", content=json.dumps({"success": False, "error": "failed"}), status="success")
    engine._extract_trace_from_messages([ai, tool])
    assert not engine._trace_tool_sequence[0].success


def test_publication_failure_rolls_back_review_and_version_records(learning_db, monkeypatch):
    from src.engine.learning_cycle import LearningCycle
    candidate = draft(); db.save_skill_draft(candidate.model_dump())
    monkeypatch.setattr(db, "_store_skill", lambda *args: (_ for _ in ()).throw(RuntimeError("controlled storage failure")))
    with pytest.raises(RuntimeError):
        LearningCycle().manual_review_skill(candidate.id, True, "review-admin")
    assert db.get_skill_draft(candidate.id)["status"] == "pending_review"
    assert db.get_published_skill_id(candidate.id) is None
    assert not db.get_all_skills()


def test_structural_verification_rejects_executable_conditions(learning_db):
    from src.services.skill_verification import SkillVerificationService
    candidate = draft()
    candidate.steps[0].condition = "__import__('os').getcwd()"
    db.save_skill_draft(candidate.model_dump())
    result = SkillVerificationService().verify_skill_draft(candidate.id)
    assert not result.verified and "condition" in result.feedback


def test_generation_source_claim_is_unique_across_database_connections(learning_db):
    from concurrent.futures import ThreadPoolExecutor
    first, second = draft("first"), draft("second")
    def save(candidate):
        return Database(db.db_path).save_learning_draft("same-source", candidate)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(save, [first, second]))
    assert results[0] == results[1]
    assert len(db.get_skill_drafts_by_user("alice")) == 1


def test_migration_quarantines_already_imported_unapproved_auto_skill(learning_db):
    candidate = draft("unapproved")
    db.save_skill_draft(candidate.model_dump())
    rogue = skill(candidate.id); rogue.metadata = {"source": "auto_generated"}
    db.save_skill(rogue)
    reopened = Database(db.db_path)
    assert reopened.get_skill(rogue.id).metadata["quarantined"]
    assert all(summary.id != rogue.id for summary in reopened.get_skills_summaries())
