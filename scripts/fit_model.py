"""Fit and persist the production hierarchy bundle.

The bundle is trained only on seasons up to and including `--through-season`;
2026-27 is deliberately excluded and scored out-of-sample.

Usage:
    TEAM_HIERARCHY_DATA=data/daily uv run python scripts/fit_model.py \
        --through-season 2025-26
"""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--through-season", default="2025-26")
    parser.add_argument("--out", type=Path, default=Path("artifacts/team_hierarchy"))
    parser.add_argument("--data", type=Path, default=None)
    return parser.parse_args()


def git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def main() -> None:
    args = parse_args()
    if args.data is not None:
        os.environ["TEAM_HIERARCHY_DATA"] = str(args.data.resolve())

    from team_hierarchy.persist import save
    from team_hierarchy.pipeline import fit_bundle

    bundle = fit_bundle(args.through_season, git_commit=git_commit())
    path = save(bundle, args.out / "model.pkl")
    print(
        f"wrote {path}  ({path.stat().st_size / 1024 / 1024:.1f} MB)\n"
        f"  trained through {args.through_season}, "
        f"{bundle.metadata['rows']:,} training rows, "
        f"{len(bundle.metadata['seasons'])} seasons"
    )
    print(f"  metadata {path.with_name('model.json')}")


if __name__ == "__main__":
    main()
