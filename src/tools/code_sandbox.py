"""Execute untrusted Python only inside a restricted Docker container."""
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from src.config import settings


def execute_python(parameters, timeout=30):
    code = parameters.get("code", "")
    if parameters.get("language", "python") != "python" or not isinstance(code, str) or not code.strip():
        return {"success": False, "error": "Nonempty Python code is required"}
    docker = shutil.which("docker")
    if not docker:
        return {"success": False, "error": "Docker is required for isolated code execution; host execution is disabled"}
    name = "hermes-" + uuid.uuid4().hex
    work = Path("workspace"); work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="code-", dir=work.resolve()) as directory:
        root = Path(directory)
        script = root / "main.py"; script.write_text(code, encoding="utf-8")
        artifacts = root / "artifacts"; artifacts.mkdir(mode=0o777); artifacts.chmod(0o777)
        command = [docker, "run", "--rm", "--pull=never", "--name", name,
            "--network=none", "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges",
            "--pids-limit=64", "--memory=256m", "--cpus=1", "--user=65534:65534",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m", "--workdir=/output",
            "--mount", f"type=bind,source={script},target=/main.py,readonly",
            "--mount", f"type=bind,source={artifacts},target=/output",
            settings.SANDBOX_CONTAINER_IMAGE, "python", "-I", "/main.py"]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=min(timeout, 120))
            if result.returncode:
                return {"success": False, "error": result.stderr[-4000:] or "Code exited unsuccessfully"}
            files = []
            candidates = list(artifacts.iterdir())
            if len(candidates) > 20 or sum(p.lstat().st_size for p in candidates) > 20 * 1024 * 1024:
                return {"success": False, "error": "Artifact limit exceeded"}
            output = Path("output") / name
            for source in candidates:
                if source.is_symlink() or not source.is_file():
                    return {"success": False, "error": "Only regular output files are accepted"}
                output.mkdir(parents=True, exist_ok=True)
                target = output / source.name
                shutil.copyfile(source, target)
                files.append(str(target))
            return {"success": True, "result": {"stdout": result.stdout[-20000:], "stderr": result.stderr[-4000:], "return_code": 0, "files": files}}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Code execution timed out"}
        except OSError as exc:
            return {"success": False, "error": str(exc)}
        finally:
            try:
                subprocess.run([docker, "rm", "-f", name], capture_output=True, timeout=10)
            except (OSError, subprocess.TimeoutExpired):
                pass
