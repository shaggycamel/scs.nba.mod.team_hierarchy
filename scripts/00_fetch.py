"""Recreate the team-hierarchy Parquet snapshot from Cockroach.

The hierarchy needs the full box-score history; only the tables it reads are
fetched. The Cockroach tables carry an implicit `rowid`, dropped before write.

Usage:
    uv run --group data python scripts/00_fetch.py --through 2026-27 --out data/daily
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import scs_hub


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--through", default="2026-27")
    parser.add_argument("--out", type=Path, default=Path("data/daily"))
    parser.add_argument("--db-con", default="cockroach-read")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    hub = scs_hub.SportsHub(db_con=args.db_con)
    through = args.through
    cutoff = hub.db.read(
        f"SELECT max(game_date) AS d FROM nba.league_game_schedule WHERE season = '{through}'"
    )["d"][0]
    if cutoff is None:
        raise SystemExit(f"no schedule for {through!r}")

    queries = {
        "nba/injuries": f"""
            SELECT * FROM nba.injuries WHERE game_date <= DATE '{cutoff}'
        """,
        "nba/league_game_schedule": f"""
            SELECT * FROM nba.league_game_schedule WHERE season <= '{through}'
        """,
        "nba/player_box_score": f"""
            SELECT * FROM nba.player_box_score
            WHERE game_id IN (
                SELECT game_id FROM nba.league_game_schedule WHERE season <= '{through}'
            )
        """,
        "nba/player_info": f"""
            SELECT * FROM nba.player_info WHERE season <= '{through}'
        """,
        "nba/team_roster_vw": f"""
            SELECT * FROM nba.team_roster_vw WHERE season <= '{through}'
        """,
        "nba/teams": "SELECT * FROM nba.teams",
        "util/player_id_map_vw": "SELECT * FROM util.player_id_map_vw",
    }

    counts = {}
    for rel, sql in queries.items():
        frame = hub.db.read(sql)
        if "rowid" in frame.columns:
            frame = frame.drop("rowid")
        out = args.out / f"{rel}.parquet"
        out.parent.mkdir(parents=True, exist_ok=True)
        frame.write_parquet(out)
        counts[rel] = frame.height
        print(f"{rel:35} {frame.height:>8,} rows  {frame.width:>2} cols")

    (args.out / "manifest.json").write_text(
        json.dumps(
            {
                "generated_at": datetime.now(UTC).isoformat(),
                "db_con": args.db_con,
                "through": through,
                "cutoff": str(cutoff),
                "rows": counts,
            },
            indent=2,
        )
        + "\n"
    )
    print(f"wrote {args.out} (cutoff {cutoff})")


if __name__ == "__main__":
    main()
