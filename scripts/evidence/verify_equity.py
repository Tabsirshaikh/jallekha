from build_equity import ROOT, build

if __name__ == "__main__":
    for path, content in build().items():
        if (ROOT / path).read_bytes() != content:
            raise SystemExit(f"Equity artifact differs: {path}")
    print("P1:E4 artifact, provenance and metrics verification passed")
