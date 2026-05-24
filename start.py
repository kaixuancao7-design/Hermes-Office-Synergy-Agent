#!/usr/bin/env python3
import os
import sys
import warnings

warnings.filterwarnings("ignore", category=UserWarning, message="pkg_resources is deprecated as an API")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from src.config import settings
from src.utils import ensure_directory
from src.logging_config import setup_logging

logger = setup_logging(settings.LOG_LEVEL)


def main():
    ensure_directory("./data")
    ensure_directory("./logs")
    ensure_directory("./workspace")
    ensure_directory("./output")
    ensure_directory("./skills")
    
    logger.info("Starting Hermes Office Synergy Agent...")
    logger.info(f"Server running on http://{settings.HOST}:{settings.PORT}")
    
    uvicorn.run(
        "src.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
        reload_dirs=["src"],
        reload_excludes=["logs", "data", "workspace", "output", "__pycache__", ".git", "*.pyc", "*.pyo", ".pytest_cache", ".tox", ".eggs", "*.egg-info"]
    )


if __name__ == "__main__":
    main()
