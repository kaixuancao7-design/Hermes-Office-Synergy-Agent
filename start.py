#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.main import app
import uvicorn
from src.config import settings
from src.utils import setup_logging, ensure_directory

logger = setup_logging(settings.LOG_LEVEL)


def main():
    ensure_directory("./data")
    ensure_directory("./logs")
    ensure_directory("./workspace")
    ensure_directory("./output")
    
    logger.info("Starting Hermes Office Synergy Agent...")
    logger.info(f"Server running on http://{settings.HOST}:{settings.PORT}")
    
    uvicorn.run(
        "src.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True
    )


if __name__ == "__main__":
    main()
