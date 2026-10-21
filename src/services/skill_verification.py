"""Structural validation of learning drafts; publication still requires human review."""
from src.types import SkillDraft, VerificationResult
from src.data.database import db
from src.utils import get_timestamp


def validate_definition(draft):
    from src.engine.skill_executor import SkillStepExecutor
    from src.plugins import get_tool_executor
    known = set(SkillStepExecutor._KNOWN_TOOL_IDS) | {"generate_outline"}
    executor = get_tool_executor()
    if executor is not None:
        known.update(executor.get_tools())
    if not draft.skill_name.strip() or not draft.description.strip():
        raise ValueError("Skill name and description are required")
    if not draft.steps or len(draft.steps) > 10:
        raise ValueError("Learning drafts must contain 1 to 10 steps")
    if not draft.trigger_patterns or any(not value.strip() for value in draft.trigger_patterns):
        raise ValueError("Nonempty trigger patterns are required")
    if len({value.casefold() for value in draft.trigger_patterns}) != len(draft.trigger_patterns):
        raise ValueError("Duplicate trigger patterns")
    ids = [step.id for step in draft.steps]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate step IDs")
    tools = 0
    for step in draft.steps:
        if not step.action.strip() or not step.id.strip():
            raise ValueError("Step ID and action are required")
        if step.next_step_id and step.next_step_id not in ids:
            raise ValueError("Unknown next_step_id")
        if step.type == "tool" or (step.type is None and step.action in known):
            tools += 1
            if step.action not in known:
                raise ValueError(f"Unknown tool: {step.action}")
        elif not step.parameters.get("instruction", "").strip():
            raise ValueError("LLM steps require a nonempty instruction")
        fallback = step.parameters.get("fallback_tool")
        if fallback and fallback not in known:
            raise ValueError("Unknown fallback tool")
        if step.condition:
            import ast
            expression = ast.parse(step.condition, mode="eval")
            allowed = (ast.Expression, ast.Name, ast.Load, ast.Attribute, ast.Subscript, ast.Constant,
                       ast.UnaryOp, ast.Not, ast.BoolOp, ast.And, ast.Or, ast.Compare, ast.Eq, ast.NotEq)
            if any(not isinstance(node, allowed) for node in ast.walk(expression)):
                raise ValueError("Unsupported condition expression")
            if any(isinstance(node, ast.Name) and node.id not in set(ids) | {"true", "false"} for node in ast.walk(expression)):
                raise ValueError("Unknown condition variable")
    if tools > 5 or sum(bool(step.condition) for step in draft.steps) > 3:
        raise ValueError("Learning draft exceeds tool/branch complexity limits")
    return True


class SkillVerificationService:
    def verify_skill_draft(self, draft_id):
        raw = db.get_skill_draft(draft_id)
        verified, feedback = False, "Draft not found"
        if raw:
            try:
                validate_definition(SkillDraft.model_validate(raw))
                verified = True
                feedback = "Structure valid. Human review required; execution quality has not been certified."
            except (ValueError, TypeError, SyntaxError) as exc:
                feedback = str(exc)
        return VerificationResult(skill_draft_id=draft_id, verified=verified, verification_type="auto",
            confidence=1.0 if verified else 0.0, feedback=feedback, similar_tasks=[], verified_at=get_timestamp())

    def list_drafts(self, user_id=None, status=None):
        if user_id is not None:
            rows = db.get_skill_drafts_by_user(user_id, status)
        else:
            import sqlite3
            with sqlite3.connect(db.db_path) as conn:
                rows = [db._row_to_draft_dict(row) for row in conn.execute(
                    "SELECT * FROM skill_drafts" + (" WHERE status=?" if status else "") + " ORDER BY created_at DESC",
                    (status,) if status else ())]
        return [SkillDraft.model_validate(row) for row in rows]


skill_verification_service = SkillVerificationService()
