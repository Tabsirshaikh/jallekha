"""Cross-platform developer tasks for JalLekha.

Usage: python tasks.py setup|test|lint|check
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
FRONTEND = ROOT / "frontend"


def run(command: list[str], *, cwd: Path = ROOT) -> None:
    print(f"+ {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def venv_python() -> str:
    windows = VENV / "Scripts" / "python.exe"
    posix = VENV / "bin" / "python"
    if windows.exists():
        return str(windows)
    if posix.exists():
        return str(posix)
    return sys.executable


def npm_command() -> str:
    return "npm.cmd" if sys.platform == "win32" else "npm"


def setup() -> None:
    if not VENV.exists():
        run([sys.executable, "-m", "venv", str(VENV)])
    python = venv_python()
    run([python, "-m", "pip", "install", "--upgrade", "pip"])
    run([python, "-m", "pip", "install", "-e", ".[dev,geo,models]"], cwd=ROOT / "backend")
    run([npm_command(), "ci"], cwd=FRONTEND)


def test() -> None:
    run([venv_python(), "-m", "pytest", "backend/tests"])
    run([npm_command(), "run", "test", "--", "--run"], cwd=FRONTEND)
    data_verifier = ROOT / "scripts" / "data" / "verify_manifest.py"
    if data_verifier.exists():
        run([venv_python(), str(data_verifier)])
    d1_verifier = ROOT / "scripts" / "data" / "verify_d1.py"
    if d1_verifier.exists():
        run([venv_python(), str(d1_verifier)])
    growth_verifier = ROOT / "scripts" / "evidence" / "verify_growth.py"
    if growth_verifier.exists():
        run([venv_python(), str(growth_verifier)])
    underserved_verifier = ROOT / "scripts" / "evidence" / "verify_underserved.py"
    if underserved_verifier.exists():
        run([venv_python(), str(underserved_verifier)])
    e1_verifier = ROOT / "scripts" / "evidence" / "verify_crosswalk.py"
    if e1_verifier.exists():
        run([venv_python(), str(e1_verifier)])

    run([venv_python(), str(ROOT / "scripts/evidence/verify_evidence.py")])


def lint() -> None:
    run(
        [
            venv_python(),
            "-m",
            "ruff",
            "check",
            "--config",
            "backend/pyproject.toml",
            "backend",
            "scripts",
            "tasks.py",
        ]
    )
    run(
        [
            venv_python(),
            "-m",
            "ruff",
            "format",
            "--config",
            "backend/pyproject.toml",
            "--check",
            "backend",
            "scripts",
            "tasks.py",
        ]
    )
    run([npm_command(), "run", "lint"], cwd=FRONTEND)
    run([npm_command(), "run", "typecheck"], cwd=FRONTEND)


def main() -> int:
    commands = {"setup": setup, "test": test, "lint": lint, "check": lambda: (test(), lint())}
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        choices = "|".join(commands)
        print(f"Usage: python tasks.py {choices}", file=sys.stderr)
        return 2
    commands[sys.argv[1]]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
