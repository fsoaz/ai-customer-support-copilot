"""Apply remediation judgments to retrieval_golden.jsonl (Task 0.7).

Requires human spot-check approval file unless --force-unverified (discouraged).
Preserves original golds in original_gold_* sidecar fields on remediated rows.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from evals.harness.paths import EVALS_ROOT, GOLDEN_PATH

JUDGMENTS_PATH = EVALS_ROOT / "datasets" / "remediation_judgments.jsonl"
SPOT_PATH = EVALS_ROOT / "datasets" / "remediation_spot_check.jsonl"
SIDECAR_PATH = EVALS_ROOT / "datasets" / "retrieval_golden_pre_remediation.jsonl"
APPLY_REPORT = EVALS_ROOT / "datasets" / "remediation_apply_report.json"


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def spot_check_ok(spot_path: Path, *, max_disagree_rate: float) -> tuple[bool, dict]:
    if not spot_path.is_file():
        return False, {"error": f"spot-check file missing: {spot_path}"}
    rows = load_jsonl(spot_path)
    reviewed = [r for r in rows if r.get("human_verdict") in ("agree", "disagree")]
    if len(reviewed) < min(20, len(rows)):
        return False, {
            "error": "spot-check incomplete",
            "reviewed": len(reviewed),
            "needed": min(20, len(rows)),
        }
    disagree = sum(1 for r in reviewed if r["human_verdict"] == "disagree")
    rate = disagree / len(reviewed) if reviewed else 1.0
    ok = rate <= max_disagree_rate
    return ok, {
        "reviewed": len(reviewed),
        "disagree": disagree,
        "disagree_rate": round(rate, 4),
        "max_disagree_rate": max_disagree_rate,
        "ok": ok,
    }


def apply_one(row: dict, judgment: dict) -> tuple[dict, str]:
    """Return updated row and action label."""
    chosen = judgment.get("chosen_doc_id") or "none"
    current = row.get("gold_doc_id") or ""
    note = judgment.get("rationale") or ""
    human_note = judgment.get("reviewer_note") or ""

    base_audit = {
        "label_source": row.get("label_source", "original"),
        "label_reviewed": True,
        "reviewer_note": human_note or note,
    }

    if chosen == "none":
        out = dict(row)
        out["original_gold_doc_id"] = current
        out["original_gold_doc_url"] = row.get("gold_doc_url", "")
        out["gold_doc_id"] = ""
        out["gold_doc_url"] = ""
        out["answerable"] = False
        out["negative_slice"] = "remediated_none"
        out["label_source"] = "remediated"
        out["label_reviewed"] = True
        out["reviewer_note"] = human_note or note or "judge: none load-bearing"
        return out, "to_unanswerable"

    if chosen == current:
        out = dict(row)
        out.update(base_audit)
        out["label_source"] = row.get("label_source") or "original"
        out["label_reviewed"] = True
        out["reviewer_note"] = human_note or note or "judge confirmed current gold"
        return out, "confirmed"

    out = dict(row)
    out["original_gold_doc_id"] = current
    out["original_gold_doc_url"] = row.get("gold_doc_url", "")
    out["gold_doc_id"] = chosen
    out["gold_doc_url"] = judgment.get("chosen_doc_url") or ""
    out["answerable"] = True
    out["label_source"] = "remediated"
    out["label_reviewed"] = True
    out["reviewer_note"] = human_note or note
    return out, "relabeled"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--golden", type=Path, default=GOLDEN_PATH)
    parser.add_argument("--judgments", type=Path, default=JUDGMENTS_PATH)
    parser.add_argument("--spot-check", type=Path, default=SPOT_PATH)
    parser.add_argument("--sidecar", type=Path, default=SIDECAR_PATH)
    parser.add_argument("--report", type=Path, default=APPLY_REPORT)
    parser.add_argument("--max-disagree-rate", type=float, default=0.15)
    parser.add_argument(
        "--force-unverified",
        action="store_true",
        help="Apply even if spot-check disagree rate exceeds threshold (not recommended)",
    )
    parser.add_argument(
        "--approved-only",
        action="store_true",
        help="Only apply judgments whose id has human_verdict=agree in spot-check "
        "(plus all non-spot rows if spot gate passes)",
    )
    args = parser.parse_args()

    if not args.golden.is_file() or not args.judgments.is_file():
        print("golden or judgments missing", file=sys.stderr)
        return 1

    ok, spot_stats = spot_check_ok(args.spot_check, max_disagree_rate=args.max_disagree_rate)
    if not ok and not args.force_unverified:
        print(f"spot-check gate failed: {spot_stats}", file=sys.stderr)
        return 2
    if not ok:
        print(f"WARNING: forcing apply despite spot-check: {spot_stats}", file=sys.stderr)

    golden = load_jsonl(args.golden)
    # Sidecar backup once.
    if not args.sidecar.is_file():
        write_jsonl(args.sidecar, golden)
        print(f"backed up golden -> {args.sidecar}")

    judgments = {j["id"]: j for j in load_jsonl(args.judgments)}
    spot_rows = load_jsonl(args.spot_check) if args.spot_check.is_file() else []
    spot_by_id = {r["id"]: r for r in spot_rows}

    # Merge human overrides from spot-check into judgments.
    for sid, srow in spot_by_id.items():
        if sid not in judgments:
            continue
        if srow.get("human_verdict") == "disagree" and srow.get("human_correction"):
            corr = srow["human_correction"]
            judgments[sid] = dict(judgments[sid])
            judgments[sid]["chosen_doc_id"] = corr.get(
                "chosen_doc_id", judgments[sid]["chosen_doc_id"]
            )
            judgments[sid]["chosen_doc_url"] = corr.get(
                "chosen_doc_url", judgments[sid].get("chosen_doc_url", "")
            )
            judgments[sid]["reviewer_note"] = srow.get("human_note") or "human correction"
        elif srow.get("human_verdict") == "agree":
            judgments[sid] = dict(judgments[sid])
            judgments[sid]["reviewer_note"] = srow.get("human_note") or judgments[sid].get(
                "rationale", ""
            )

    counts = {"relabeled": 0, "confirmed": 0, "to_unanswerable": 0, "untouched": 0}
    out_rows: list[dict] = []
    for row in golden:
        rid = row.get("id")
        if rid not in judgments:
            # Still stamp default audit fields on answerable rows for schema consistency.
            if row.get("answerable"):
                updated = dict(row)
                updated.setdefault("label_source", "original")
                updated.setdefault("label_reviewed", False)
                updated.setdefault("reviewer_note", "")
                out_rows.append(updated)
            else:
                out_rows.append(row)
            counts["untouched"] += 1
            continue

        if args.approved_only and rid in spot_by_id:
            if spot_by_id[rid].get("human_verdict") != "agree":
                # Skip disagreed without correction already handled above.
                if spot_by_id[rid].get("human_verdict") == "disagree" and not spot_by_id[rid].get(
                    "human_correction"
                ):
                    updated = dict(row)
                    updated["label_reviewed"] = True
                    updated["reviewer_note"] = "spot disagree without correction; left unchanged"
                    out_rows.append(updated)
                    counts["untouched"] += 1
                    continue

        updated, action = apply_one(row, judgments[rid])
        out_rows.append(updated)
        counts[action] = counts.get(action, 0) + 1

    write_jsonl(args.golden, out_rows)
    answerable = sum(1 for r in out_rows if r.get("answerable"))
    unanswerable = len(out_rows) - answerable
    report = {
        "counts": counts,
        "answerable": answerable,
        "unanswerable": unanswerable,
        "spot_stats": spot_stats,
        "forced": bool(args.force_unverified and not ok),
    }
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"wrote {args.golden}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
