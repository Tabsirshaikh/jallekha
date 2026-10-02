"""Guard the integrated dependency history and reject unresolved conflict markers."""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PR_HEADS = {
    3: "227591f7cb3e8c5edeb456219c3407db3722973b",
    4: "3f4bf2a326ceb598ce86ad95f47c65c8ba2cfc3e",
    9: "ff3006039307264b423eef925fa72d6dd36b7ca6",
    10: "ac223b6f3e43fb9193c2cca39a12ec5f9ecf1e46",
}


def main() -> None:
    for number, commit in PR_HEADS.items():
        subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=ROOT, check=True)
        print(f"PR #{number} head preserved")
    files = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    for filename in filter(None, files):
        path = ROOT / filename
        if path.suffix in {".py", ".md", ".csv", ".yml", ".yaml", ".ts", ".tsx"}:
            if re.search(r"^(?:<<<<<<< |>>>>>>> )", path.read_text(encoding="utf-8-sig"), re.M):
                raise SystemExit(f"Unresolved conflict marker: {filename}")
    print("P1 integration history and conflict checks passed")


if __name__ == "__main__":
    main()
