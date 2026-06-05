"""端到端集成测试：技能自学习管道"""
import sys, os, json, asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils import generate_id, get_timestamp
from src.types import ExecutionTrace, ToolCallRecord, Skill, SkillStep

print("=== Test 1: ExecutionTrace types ===")
trace = ExecutionTrace(
    trace_id='test-001', user_id='u1', query='test query',
    tool_sequence=[
        ToolCallRecord(tool_id='web_search', parameters={'q': 'test'}, result='found', success=True, step_index=1),
        ToolCallRecord(tool_id='feishu_file_read', parameters={'file_key': 'abc'}, result='content', success=True, step_index=2),
        ToolCallRecord(tool_id='code_execution', parameters={'code': 'print(1)'}, result='1', success=True, step_index=3),
    ],
    final_response='All done!', step_count=3, mode='manual_loop', created_at=get_timestamp(),
)
print(f"  OK: ExecutionTrace | tool_calls={len(trace.tool_sequence)} | mode={trace.mode}")

print()
print("=== Test 2: Database execution_traces CRUD ===")
from src.data.database import db
db.save_execution_trace(trace.model_dump())
loaded = db.get_execution_trace('test-001')
assert loaded is not None, 'Failed to load trace'
assert loaded['step_count'] == 3
assert len(loaded['tool_sequence']) == 3
print(f"  OK: save + load execution trace")

traces = db.get_recent_traces('u1', limit=5)
assert any(t['trace_id'] == 'test-001' for t in traces)
print(f"  OK: get_recent_traces returned {len(traces)} traces")

print()
print("=== Test 3: Skill usage recording ===")
skill_obj = Skill(
    id='skill-test-001', name='Test Learned Skill', description='test',
    type='learned', trigger_patterns=['test'], steps=[],
    metadata={}, created_at=get_timestamp(), updated_at=get_timestamp(), created_by='system',
)
db.save_skill(skill_obj)
db.record_skill_usage('skill-test-001', 'u1', 'test-001', True)
db.record_skill_usage('skill-test-001', 'u2', None, True)
stats = db.get_skill_usage_stats('skill-test-001')
assert stats['total_uses'] == 2
assert stats['success_rate'] == 100.0
print(f"  OK: skill_usage stats = {stats}")

all_usage = db.get_all_learned_skill_usage()
print(f"  OK: get_all_learned_skill_usage returned {len(all_usage)} skills")

print()
print("=== Test 4: SKILL.md Manager ===")
from src.skills.skill_md import skill_md_manager

md = skill_md_manager.skill_to_markdown(skill_obj)
assert '---' in md and '# Test Learned Skill' in md and '## Description' in md
print(f"  OK: skill_to_markdown produced {len(md)} chars")

parsed = skill_md_manager.markdown_to_skill(md)
assert parsed is not None and parsed.name == 'Test Learned Skill' and parsed.type == 'learned'
print(f"  OK: markdown_to_skill roundtripped correctly")

filepath = skill_md_manager.write_skill_md(skill_obj)
assert os.path.exists(filepath)
read_back = skill_md_manager.read_skill_md(filepath)
assert read_back is not None and read_back.name == 'Test Learned Skill'
print(f"  OK: write + read SKILL.md roundtrip")

synced = skill_md_manager.sync_from_directory()
print(f"  OK: sync_from_directory found {len(synced)} skills")

skill_md_manager.delete_skill_md('Test Learned Skill')
assert not os.path.exists(filepath)
print(f"  OK: delete SKILL.md")

print()
print("=== Test 5: Background Scheduler ===")
from src.engine.scheduler import BackgroundScheduler

async def test_scheduler():
    s = BackgroundScheduler()
    executed = []
    async def test_coro():
        executed.append(True)
    await s.start()
    await s.add_one_shot('test_task', test_coro, delay_seconds=0)
    await asyncio.sleep(0.3)
    await s.stop()
    assert len(executed) > 0, 'One-shot task did not execute'
    print(f"  OK: one-shot task executed + scheduler stopped")

asyncio.run(test_scheduler())

print()
print("=== Test 6: Skill Auto-Generator ===")
from src.engine.skill_generator import SkillAutoGenerator

gen = SkillAutoGenerator()
simple_trace = ExecutionTrace(
    trace_id='simple-001', user_id='u1', query='hello',
    tool_sequence=[ToolCallRecord(tool_id='web_search', parameters={}, result='hi', step_index=1)],
    final_response='Hi!', step_count=1, mode='manual_loop', created_at=get_timestamp(),
)
assert not gen.should_trigger(simple_trace), 'Simple trace should NOT trigger'

complex_trace = ExecutionTrace(
    trace_id='complex-001', user_id='u1', query='complex task',
    tool_sequence=[ToolCallRecord(tool_id=f'tool_{i}', parameters={}, result=f'r{i}', step_index=i) for i in range(6)],
    final_response='Done!', step_count=6, mode='manual_loop', created_at=get_timestamp(),
)
assert gen.should_trigger(complex_trace), 'Complex trace SHOULD trigger'
print(f"  OK: should_trigger works (simple=False, complex=True)")

prompt = gen._build_prompt(complex_trace)
assert 'complex task' in prompt and 'tool_0' in prompt
print(f"  OK: _build_prompt generated {len(prompt)} chars")

bad_json = 'some text {"skill_name": "test", "confidence": 0.5} extra'
parsed = gen._parse_llm_response(bad_json)
assert parsed is not None and parsed['skill_name'] == 'test'
print(f"  OK: _parse_llm_response extracts JSON from text")

print()
print("=== Test 7: Skill Auto-Patcher ===")
from src.engine.skill_patcher import SkillAutoPatcher

patcher = SkillAutoPatcher()
score = patcher._calculate_relevance(skill_obj, 'this is a test of the learned skill')
assert score >= 0.3, f'Relevance score too low: {score}'
print(f"  OK: _calculate_relevance = {score:.2f}")

no_score = patcher._calculate_relevance(skill_obj, 'completely unrelated topic')
assert no_score < 0.5
print(f"  OK: unrelated relevance = {no_score:.2f}")

print()
print("=== Test 8: Full pipeline (save trace -> check trigger) ===")
db.save_execution_trace(complex_trace.model_dump())
loaded_trace = ExecutionTrace(**db.get_execution_trace('complex-001'))
assert gen.should_trigger(loaded_trace)
print(f"  OK: Full pipeline: save -> load -> check trigger")

print()
print("=== ALL 8 TESTS PASSED ===")
