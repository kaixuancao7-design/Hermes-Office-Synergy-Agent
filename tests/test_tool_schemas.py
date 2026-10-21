def test_legacy_checks():
    """验证改造 1+2+3：OpenAI/MCP 工具 schema 导出 + SkillStep.type 字段 + 旧技能迁移

    运行方式: python tests/test_tool_schemas.py
    """
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from src.types import Skill, SkillStep
    from src.utils import generate_id, get_timestamp


    # ============================================================================
    # 改造 1: OpenAI / Anthropic 工具 Schema
    # ============================================================================

    print("=== Test 1: OpenAI schema shape ===")
    from src.engine.langchain_tools import get_tool_schemas_openai, get_tool_descriptors_mcp

    schemas = get_tool_schemas_openai()
    assert isinstance(schemas, list) and len(schemas) > 0, "should return non-empty list"
    for item in schemas:
        assert set(item.keys()) == {"name", "description", "parameters"}, f"unexpected keys: {item.keys()}"
        params = item["parameters"]
        assert params["type"] == "object", f"parameters.type should be object, got {params.get('type')}"
        assert isinstance(params["properties"], dict), "properties should be dict"
        assert isinstance(params["required"], list), "required should be list"
        assert "title" not in params, "title should be stripped"
        assert "$defs" not in params, "$defs should be stripped"
    print(f"  OK: {len(schemas)} schemas, all valid OpenAI format")

    print()
    print("=== Test 2: OpenAI schema subset ===")
    subset = get_tool_schemas_openai(["web_search", "memory_search"])
    assert len(subset) == 2, f"expected 2, got {len(subset)}"
    assert {s["name"] for s in subset} == {"web_search", "memory_search"}
    print(f"  OK: subset returns {len(subset)} tools")

    print()
    print("=== Test 3: MCP descriptor shape ===")
    mcp_descs = get_tool_descriptors_mcp()
    assert len(mcp_descs) == len(schemas), "MCP count should match OpenAI count"
    for item in mcp_descs:
        assert set(item.keys()) == {"name", "description", "inputSchema"}, f"unexpected keys: {item.keys()}"
        args = item["inputSchema"]
        assert args["type"] == "object", f"arguments.type should be object, got {args.get('type')}"
        assert isinstance(args["properties"], dict)
        assert isinstance(args["required"], list)
        assert "parameters" not in item, "MCP should use 'inputSchema' not 'parameters'"
    print(f"  OK: {len(mcp_descs)} MCP descriptors, all use 'inputSchema' field")

    print()
    print("=== Test 4: Optional field flattened (no anyOf) ===")
    # FeishuFileReadInput has user_id with default="" → Optional → anyOf in raw schema
    feishu_schema = get_tool_schemas_openai(["feishu_file_read"])[0]
    props = feishu_schema["parameters"]["properties"]
    for name, prop in props.items():
        assert "anyOf" not in prop, f"property '{name}' still has anyOf: {prop}"
    print(f"  OK: all properties flattened, no anyOf remaining")


    # ============================================================================
    # 改造 3: SkillStep.type 字段
    # ============================================================================

    print()
    print("=== Test 5: SkillStep.type default None ===")
    step = SkillStep(id="s1", action="x", parameters={})
    assert step.type is None, f"default should be None, got {step.type}"
    print("  OK: default type is None")

    print()
    print("=== Test 6: SkillStep.type explicit ===")
    step_tool = SkillStep(id="s1", action="web_search", type="tool", parameters={})
    step_llm = SkillStep(id="s2", action="analyze_input", type="llm", parameters={})
    assert step_tool.type == "tool"
    assert step_llm.type == "llm"
    print("  OK: explicit type preserved")


    # ============================================================================
    # 改造 3.3: SKILL.md Type 行 roundtrip
    # ============================================================================

    print()
    print("=== Test 7: SKILL.md roundtrip with type ===")
    from src.skills.skill_md import SkillMarkdownManager

    md_mgr = SkillMarkdownManager(base_dir="./data/test_skill_md_tmp")
    os.makedirs(md_mgr.base_dir, exist_ok=True)

    test_skill = Skill(
        id="test-type-roundtrip", name="Test Type Skill", description="test",
        type="learned", trigger_patterns=["test"],
        steps=[
            SkillStep(id=generate_id(), action="web_search", type="tool", parameters={"query": "q"}),
            SkillStep(id=generate_id(), action="analyze_input", type="llm", parameters={"instruction": "i"}),
        ],
        metadata={}, created_at=get_timestamp(), updated_at=get_timestamp(), created_by="test",
    )
    filepath = md_mgr.write_skill_md(test_skill)
    loaded = md_mgr.read_skill_md(filepath)
    assert loaded is not None, "failed to load roundtrip skill"
    assert len(loaded.steps) == 2
    assert loaded.steps[0].type == "tool", f"step0 type={loaded.steps[0].type}"
    assert loaded.steps[1].type == "llm", f"step1 type={loaded.steps[1].type}"
    print("  OK: roundtrip preserves type field")

    print()
    print("=== Test 8: SKILL.md backward compat (no Type line) ===")
    legacy_md = """---
    name: Legacy Skill
    description: legacy
    version: 1.0.0
    type: learned
    triggers:
      - legacy
    created_by: system
    created_at: 0
    updated_at: 0
    ---

    # Legacy Skill

    ## Description

    legacy

    ## Steps

    ### Step 1: web_search

    - **Action**: web_search
    - **Parameters**:
      - `query`: test
    """
    legacy_path = os.path.join(md_mgr.base_dir, "legacy_test.md")
    with open(legacy_path, "w", encoding="utf-8") as f:
        f.write(legacy_md)
    legacy_skill = md_mgr.read_skill_md(legacy_path)
    assert legacy_skill is not None
    assert legacy_skill.steps[0].type is None, f"legacy step type should be None, got {legacy_skill.steps[0].type}"
    print("  OK: legacy MD (no Type line) → type=None (backward compat)")


    # ============================================================================
    # 改造 3.6: 旧技能迁移幂等性
    # ============================================================================

    print()
    print("=== Test 9: migrate_md_files_add_type idempotent ===")
    # legacy_test.md still has type=None (from Test 8)
    files1, steps1 = md_mgr.migrate_md_files_add_type()
    assert steps1 > 0, "first migration should migrate some steps"
    # write_skill_md writes by skill.name → "Legacy Skill.md"; reload from there
    migrated_path = os.path.join(md_mgr.base_dir, "Legacy Skill.md")
    migrated_skill = md_mgr.read_skill_md(migrated_path)
    assert migrated_skill is not None, "migrated file should exist"
    assert migrated_skill.steps[0].type == "tool", f"after migration type={migrated_skill.steps[0].type}"
    # remove the original legacy file (write_skill_md writes by name, won't touch original)
    if os.path.exists(legacy_path):
        os.unlink(legacy_path)
    # second run should be no-op (all steps now have type)
    files2, steps2 = md_mgr.migrate_md_files_add_type()
    assert steps2 == 0, f"second migration should migrate 0 steps, got {steps2}"
    print(f"  OK: first run migrated {steps1} steps, second run {steps2} (idempotent)")


    # ============================================================================
    # 改造 3.2: 执行器 None 回退
    # ============================================================================

    print()
    print("=== Test 10: executor fallback for type=None ===")
    from src.engine.skill_executor import skill_executor
    # _is_tool_action should classify known tools as tool, others as llm
    assert skill_executor._is_tool_action("web_search") is True, "web_search should be tool"
    assert skill_executor._is_tool_action("analyze_input") is False, "analyze_input should be llm"
    # type=None → inferred: web_search→tool, analyze_input→llm
    assert ("tool" if (skill_executor._is_tool_action("web_search")) else "llm") == "tool"
    assert ("tool" if (skill_executor._is_tool_action("analyze_input")) else "llm") == "llm"
    print("  OK: type=None falls back to _is_tool_action inference")


    # 清理测试文件
    import shutil
    if os.path.exists("./data/test_skill_md_tmp"):
        shutil.rmtree("./data/test_skill_md_tmp")

    print()
    print("=" * 50)
    print("ALL TESTS PASSED")
    print("=" * 50)


if __name__ == "__main__":
    test_legacy_checks()
