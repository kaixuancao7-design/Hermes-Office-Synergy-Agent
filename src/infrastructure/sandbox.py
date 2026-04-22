import subprocess
import os
import shutil
from typing import Optional, Tuple, Dict, Any
from src.logging_config import get_logger

logger = get_logger("tool")


class SandboxConfig:
    def __init__(self):
        self.enabled: bool = True
        self.allowed_paths: list = ["./workspace", "./output"]
        self.max_execution_time: int = 60
        self.max_memory_mb: int = 512


class Sandbox:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = SandboxConfig()
        if config:
            for key, value in config.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
        self._ensure_directories()
    
    def _ensure_directories(self):
        for dir_path in self.config.allowed_paths:
            os.makedirs(dir_path, exist_ok=True)
    
    def execute_script(
        self,
        script: str,
        script_type: str
    ) -> Tuple[str, str, bool]:
        if not self.config.enabled:
            return self._execute_unsafe(script, script_type)
        
        script_path = self._write_script(script, script_type)
        return self._run_in_sandbox(script_path, script_type)
    
    def _write_script(self, script: str, script_type: str) -> str:
        extension = {
            "python": ".py",
            "javascript": ".js",
            "shell": ".sh"
        }.get(script_type, ".txt")
        
        script_path = os.path.join(
            "./workspace",
            f"script_{os.times()[4]}{extension}"
        )
        
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script)
        
        return script_path
    
    def _execute_unsafe(
        self,
        script: str,
        script_type: str
    ) -> Tuple[str, str, bool]:
        script_path = self._write_script(script, script_type)
        
        try:
            command: list
            if script_type == "python":
                command = ["python", script_path]
            elif script_type == "javascript":
                command = ["node", script_path]
            elif script_type == "shell":
                command = ["bash", script_path]
            else:
                return "", "Unsupported script type", False
            
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.config.max_execution_time
            )
            
            return result.stdout, result.stderr, result.returncode == 0
        
        except subprocess.TimeoutExpired:
            return "", "Execution timed out", False
        finally:
            if os.path.exists(script_path):
                os.remove(script_path)
    
    def _run_in_sandbox(
        self,
        script_path: str,
        script_type: str
    ) -> Tuple[str, str, bool]:
        logger.info(f"Running script in sandbox: {script_path}")
        
        with open(script_path, "r", encoding="utf-8") as f:
            script_content = f.read()
        
        return self._execute_unsafe(script_content, script_type)
    
    def validate_path(self, file_path: str) -> bool:
        resolved_path = os.path.abspath(file_path)
        return any(
            resolved_path.startswith(os.path.abspath(allowed))
            for allowed in self.config.allowed_paths
        )
    
    def read_file(self, file_path: str) -> Optional[str]:
        if not self.validate_path(file_path):
            logger.warning(f"Access denied to path: {file_path}")
            return None
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read file: {str(e)}")
            return None
    
    def write_file(self, file_path: str, content: str) -> bool:
        if not self.validate_path(file_path):
            logger.warning(f"Access denied to path: {file_path}")
            return False
        
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        except Exception as e:
            logger.error(f"Failed to write file: {str(e)}")
            return False
    
    def list_files(self, directory: str) -> Optional[list]:
        if not self.validate_path(directory):
            logger.warning(f"Access denied to directory: {directory}")
            return None
        
        try:
            return os.listdir(directory)
        except Exception as e:
            logger.error(f"Failed to list files: {str(e)}")
            return None
    
    def cleanup(self):
        workspace_dir = "./workspace"
        if os.path.exists(workspace_dir):
            shutil.rmtree(workspace_dir)
            os.makedirs(workspace_dir)


sandbox = Sandbox()
