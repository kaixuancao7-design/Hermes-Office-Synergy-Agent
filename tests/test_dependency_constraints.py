from pathlib import Path
from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[1]


def requirements(path):
    return [Requirement(line.split("#", 1)[0].strip()) for line in path.read_text(encoding="utf-8-sig").splitlines()
            if line.split("#", 1)[0].strip()]


def test_constraints_cover_direct_requirements_and_satisfy_declared_bounds():
    pins = {req.name.lower().replace("_", "-"): req for req in requirements(ROOT / "constraints-py312.txt")}
    for req in requirements(ROOT / "requirements.txt"):
        pin = pins[req.name.lower().replace("_", "-")]
        specs = list(pin.specifier)
        assert len(specs) == 1 and specs[0].operator == "=="
        assert req.specifier.contains(specs[0].version)
