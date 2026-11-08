"""Publish a daily depth-chart file to `mod.team_hierarchy`.

Usage:
    uv run --group data python scripts/publish.py \
        --input artifacts/team_hierarchy_2026-11-07.parquet
"""

from __future__ import annotations

import argparse
from pathlib import Path

import polars as pl
import scs_hub
from sqlalchemy import text

PUBLIC_TABLE = "mod.team_hierarchy"
TABLE = "mod.team_hierarchy_base"

DDL = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
  game_date date NOT NULL,
  game_id bigint NOT NULL,
  team_id bigint NOT NULL,
  player_id bigint NOT NULL,
  season text,
  team_abbreviation text,
  opponent text,
  home boolean,
  player_name text,
  position text,
  position_depth bigint,
  height_cm bigint,
  report_status text,
  p_play double precision,
  minutes_if_plays double precision,
  expected_minutes double precision,
  expected_usage double precision,
  depth_rank bigint,
  available_rank bigint,
  rank_improvement bigint,
  expected_vacated_minutes double precision,
  expected_vacated_minutes_same_position double precision,
  model_cutoff text,
  model_version text,
  generated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (game_date, game_id, team_id, player_id)
)
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--db-con", default="cockroach-write")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    frame = pl.read_parquet(args.input)
    if frame.is_empty():
        print(f"{args.input}: no rows; nothing to publish")
        return
    hub = scs_hub.SportsHub(db_con=args.db_con)
    dates = frame["game_date"].unique().to_list()
    with hub.db.engine.begin() as conn:
        conn.execute(text(DDL))
        # The table predates the provenance columns.
        conn.execute(text(f"ALTER TABLE {TABLE} ADD COLUMN IF NOT EXISTS model_cutoff text"))
        conn.execute(text(f"ALTER TABLE {TABLE} ADD COLUMN IF NOT EXISTS model_version text"))
        for d in dates:
            conn.execute(text(f"DELETE FROM {TABLE} WHERE game_date = DATE '{d}'"))
        frame.write_database(TABLE, conn, if_table_exists="append")
        conn.execute(
            text(
                f"CREATE OR REPLACE VIEW {PUBLIC_TABLE} AS "
                f"SELECT * FROM {TABLE}"
            )
        )
        conn.execute(text(f"GRANT SELECT ON {PUBLIC_TABLE} TO kobe_public"))
        conn.execute(text(f"REVOKE SELECT ON {TABLE} FROM kobe_public"))

    count = hub.db.read(f"SELECT count(*) AS n FROM {PUBLIC_TABLE}").item()
    print(
        f"{args.db_con}: wrote {frame.height:,} rows across {len(dates)} dates "
        f"to {PUBLIC_TABLE} (table now {count:,})"
    )


if __name__ == "__main__":
    main()
