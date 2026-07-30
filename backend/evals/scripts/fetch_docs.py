"""Fetch Auth0 documentation source (MIT) into corpus/auth0/docs/raw.

Fetch is separated from parsing so the manifest can be rebuilt without re-cloning.
The expected commit pin is required (BUG-008): silent HEAD drift is a hard failure.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_URL = "https://github.com/auth0/docs.git"
USER_AGENT = "CorpCorpusBot/0.1 (+local-research; Stage0 eval corpus)"

ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "corpus" / "auth0" / "docs"
RAW_DIR = DOCS_DIR / "raw"
META_PATH = DOCS_DIR / "fetch_meta.json"
PIN_PATH = DOCS_DIR / "expected_commit.txt"


def expected_commit() -> str:
    if not PIN_PATH.exists():
        raise FileNotFoundError(
            f"missing pin file {PIN_PATH}; refuse to clone unpinned HEAD (BUG-008)"
        )
    pin = PIN_PATH.read_text(encoding="utf-8").strip().splitlines()[0].strip()
    if len(pin) < 7:
        raise ValueError(f"invalid pin in {PIN_PATH}: {pin!r}")
    return pin


def fetch(*, force: bool = False, commit: str | None = None) -> str:
    pin = commit or expected_commit()
    RAW_DIR.parent.mkdir(parents=True, exist_ok=True)

    if RAW_DIR.exists() and (RAW_DIR / ".git").exists() and not force:
        sha = _git_sha(RAW_DIR)
        if not sha.startswith(pin) and not pin.startswith(sha):
            raise RuntimeError(
                f"docs raw SHA {sha} does not match pin {pin}. "
                f"Re-run with --force to re-clone the pinned commit."
            )
        print(f"docs raw already present at {RAW_DIR} (commit {sha}); pin ok")
        _write_meta(sha)
        return sha

    if RAW_DIR.exists():
        shutil.rmtree(RAW_DIR)

    subprocess.run(
        ["git", "clone", "--filter=blob:none", "--no-checkout", REPO_URL, str(RAW_DIR)],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(RAW_DIR), "fetch", "--depth", "1", "origin", pin],
        check=True,
    )
    subprocess.run(["git", "-C", str(RAW_DIR), "checkout", pin], check=True)

    sha = _git_sha(RAW_DIR)
    if not sha.startswith(pin) and not pin.startswith(sha):
        raise RuntimeError(f"checked out {sha} but pin is {pin}")
    _write_meta(sha)
    print(f"fetched auth0/docs @ {sha} → {RAW_DIR}")
    return sha


def _git_sha(repo: Path) -> str:
    out = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True)
    return out.strip()


def _write_meta(sha: str) -> None:
    META_PATH.write_text(
        json.dumps(
            {
                "repo": REPO_URL,
                "commit": sha,
                "expected_commit_file": str(PIN_PATH.relative_to(ROOT)),
                "license": "MIT",
                "user_agent_note": USER_AGENT,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--commit",
        default=None,
        help="Override pin (defaults to expected_commit.txt)",
    )
    parser.add_argument("--force", action="store_true", help="Re-clone even if raw exists")
    args = parser.parse_args()
    try:
        fetch(commit=args.commit, force=args.force)
    except (subprocess.CalledProcessError, FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"fetch_docs failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
