"""Fetch Auth0 documentation source (MIT) into corpus/auth0/docs/raw.

Fetch is separated from parsing so the manifest can be rebuilt without re-cloning.
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
RAW_DIR = ROOT / "corpus" / "auth0" / "docs" / "raw"
META_PATH = ROOT / "corpus" / "auth0" / "docs" / "fetch_meta.json"


def fetch(commit: str | None = None, force: bool = False) -> str:
    RAW_DIR.parent.mkdir(parents=True, exist_ok=True)
    if RAW_DIR.exists() and any(RAW_DIR.iterdir()) and not force:
        sha = _git_sha(RAW_DIR)
        print(f"docs raw already present at {RAW_DIR} (commit {sha}); use --force to re-fetch")
        _write_meta(sha)
        return sha

    if RAW_DIR.exists():
        shutil.rmtree(RAW_DIR)

    cmd = [
        "git",
        "clone",
        "--depth",
        "1",
        "--single-branch",
        REPO_URL,
        str(RAW_DIR),
    ]
    if commit:
        # shallow clone of a specific commit needs fetch after
        cmd = ["git", "clone", "--filter=blob:none", "--no-checkout", REPO_URL, str(RAW_DIR)]
        subprocess.run(cmd, check=True)
        subprocess.run(
            ["git", "-C", str(RAW_DIR), "fetch", "--depth", "1", "origin", commit],
            check=True,
        )
        subprocess.run(["git", "-C", str(RAW_DIR), "checkout", commit], check=True)
    else:
        subprocess.run(cmd, check=True)

    sha = _git_sha(RAW_DIR)
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
    parser.add_argument("--commit", default=None, help="Optional commit SHA to pin")
    parser.add_argument("--force", action="store_true", help="Re-clone even if raw exists")
    args = parser.parse_args()
    try:
        fetch(commit=args.commit, force=args.force)
    except subprocess.CalledProcessError as exc:
        print(f"git failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
