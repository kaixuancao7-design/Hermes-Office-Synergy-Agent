import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.config import settings


@pytest.fixture(scope="module")
def client():
    """创建测试客户端"""
    with TestClient(app) as client:
        yield client


class TestAPIEndpoints:
    """API端点测试"""

    def test_root_endpoint(self, client):
        """测试根端点"""
        response = client.get("/")
        assert response.status_code == 200
        assert "Hermes Office Synergy Agent" in response.json()["message"]

    def test_health_check(self, client):
        """测试健康检查端点"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_send_message(self, client):
        """测试发送消息端点"""
        response = client.post(
            "/api/v1/message",
            json={
                "user_id": "test_user",
                "content": "Hello, Agent!",
                "metadata": {"source": "test"}
            }
        )
        assert response.status_code == 200
        assert "response" in response.json()

    def test_send_message_empty_content(self, client):
        """测试发送空消息"""
        response = client.post(
            "/api/v1/message",
            json={
                "user_id": "test_user",
                "content": "",
                "metadata": {"source": "test"}
            }
        )
        assert response.status_code == 200  # 应该成功处理

    def test_get_skills(self, client):
        """测试获取技能列表端点"""
        response = client.get("/api/v1/skills")
        assert response.status_code == 200
        assert "skills" in response.json()
        assert isinstance(response.json()["skills"], list)

    def test_create_skill(self, client):
        """测试创建技能端点"""
        response = client.post(
            "/api/v1/skills",
            json={
                "user_id": "test_user",
                "name": "Test Skill",
                "description": "A test skill",
                "steps": [
                    {"id": "step1", "action": "test_action", "parameters": {"key": "value"}}
                ]
            }
        )
        assert response.status_code == 200
        assert "skill" in response.json()
        assert response.json()["skill"]["name"] == "Test Skill"

    def test_create_skill_missing_fields(self, client):
        """测试创建技能缺少必填字段"""
        response = client.post(
            "/api/v1/skills",
            json={
                "user_id": "test_user",
                # 缺少name和steps
            }
        )
        assert response.status_code == 400

    def test_get_skill_not_found(self, client):
        """测试获取不存在的技能"""
        response = client.get("/api/v1/skills/nonexistent_skill_id")
        assert response.status_code == 404

    def test_execute_skill(self, client):
        """测试执行技能端点"""
        # 先创建一个技能
        create_response = client.post(
            "/api/v1/skills",
            json={
                "user_id": "test_user",
                "name": "Executable Skill",
                "description": "Skill for testing execution",
                "steps": [
                    {"id": "step1", "action": "open_app", "parameters": {"app": "notepad"}}
                ]
            }
        )
        skill_id = create_response.json()["skill"]["id"]
        
        # 执行技能
        response = client.post(f"/api/v1/skills/{skill_id}/execute")
        assert response.status_code == 200
        assert "results" in response.json()

    def test_execute_skill_not_found(self, client):
        """测试执行不存在的技能"""
        response = client.post("/api/v1/skills/nonexistent/execute")
        assert response.status_code == 404

    def test_get_user_profile_not_found(self, client):
        """测试获取不存在的用户"""
        response = client.get("/api/v1/user/nonexistent_user")
        assert response.status_code == 404

    def test_update_user_profile(self, client):
        """测试更新用户资料"""
        response = client.put(
            "/api/v1/user/test_user",
            json={"name": "Updated Name", "role": "admin"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "success"

    def test_search_memory(self, client):
        """测试搜索记忆端点"""
        response = client.get("/api/v1/memory/search", params={
            "user_id": "test_user",
            "query": "test query"
        })
        assert response.status_code == 200
        assert "results" in response.json()

    def test_submit_feedback(self, client):
        """测试提交反馈端点"""
        response = client.post(
            "/api/v1/feedback",
            json={
                "user_id": "test_user",
                "original": "Original response",
                "corrected": "Corrected response",
                "context": "Test context"
            }
        )
        assert response.status_code == 200
        assert response.json()["status"] == "success"

    def test_register_im_adapter(self, client):
        """测试注册IM适配器端点"""
        response = client.post(
            "/api/v1/adapters/register",
            json={
                "type": "feishu",
                "enabled": False,
                "config": {"app_id": "test_id", "app_secret": "test_secret"}
            }
        )
        assert response.status_code == 200
        assert response.json()["status"] == "success"
