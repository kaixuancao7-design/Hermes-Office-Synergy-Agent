import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import settings
from src.data.database import db
from src.utils import ensure_directory

@pytest.fixture(scope="session")
def test_settings():
    """测试配置"""
    settings.DATABASE_PATH = "./data/test_agent.db"
    settings.VECTOR_DB_PATH = "./data/test_vectors"
    return settings

@pytest.fixture(scope="session")
def test_database(test_settings):
    """测试数据库连接"""
    ensure_directory("./data")
    # 使用测试数据库
    test_db = type(db)(test_settings.DATABASE_PATH)
    yield test_db
    # 清理测试数据
    if os.path.exists(test_settings.DATABASE_PATH):
        os.remove(test_settings.DATABASE_PATH)

@pytest.fixture(scope="function")
def clean_database(test_database):
    """每个测试前清理数据库"""
    # 可以在这里添加清理逻辑
    yield test_database
