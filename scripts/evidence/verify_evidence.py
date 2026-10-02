"""Verify committed E2 artifacts against a fresh in-memory computation."""

from build_evidence import ROOT, build

if __name__ == "__main__":
    for name, content in build().items():
        if (ROOT / name).read_bytes() != content:
            raise SystemExit(f"E2 artifact differs: {name}; rebuild and review changes")
    print("E2 input hashes, formulas and committed artifacts verified.")
