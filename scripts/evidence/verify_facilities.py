"""Verify committed D9 facility artifacts against a fresh in-memory computation."""

from build_facilities import ROOT, build

if __name__ == "__main__":
    for name, content in build().items():
        if (ROOT / name).read_bytes() != content:
            raise SystemExit(f"D9 artifact differs: {name}; rebuild and review changes")
    print("D9 input hashes, classification and committed ward counts verified.")
