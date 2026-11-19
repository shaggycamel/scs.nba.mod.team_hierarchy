"""Build the team archetype distribution and depth summary.

One row per team-game-archetype with three shares (expected starters, actual
starters, available players) and the top three players for that style. This is
descriptive output: it does not feed the absorption model.

Usage:
    uv run --group data python scripts/build_team_archetype_summary.py \
        --season 2026-27
    uv run --group data python scripts/build_team_archetype_summary.py \
        --season 2025-26 \
        --assignments ../player_archetypes/artifacts/backfill/assignments.parquet
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
from sqlalchemy import text

from team_hierarchy.roster import build_panel
from team_hierarchy.similarity import attach_responsibilities
from team_hierarchy.state import add_pre_game_state
from team_hierarchy.team_archetype import team_archetype_summary

ROOT = Path(__file__).resolve().parent.parent
TABLE = "team_archetype_summary_base"
SCHEMA = "mod"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", required=True)
    parser.add_argument("--assignments", type=Path, default=None)
    parser.add_argument("--db-con", default="jetson-write")
    parser.add_argument("--out", type=Path, default=Path("artifacts/team_archetype_summary"))
    parser.add_argument("--publish", action="store_true")
    return parser.parse_args()


def load_assignments(args: argparse.Namespace) -> pl.DataFrame:
    if args.assignments is not None:
        frame = pl.read_parquet(args.assignments).filter(pl.col("season") == args.season)
        version = None
        if "model_version" in frame.columns:
            version = frame["model_version"].max()
        elif "model_cutoff" in frame.columns and "model_checksum" in frame.columns:
            frame = frame.with_columns(
                model_version=pl.format(
                    "{}.{}",
                    pl.col("model_cutoff"),
                    pl.col("model_checksum").str.slice(0, 8),
                )
            )
            version = frame["model_version"].max()
        if version is None:
            raise ValueError("assignments carry no model_version")
        return frame.with_columns(pl.lit(version).alias("model_version"))

    from scs_hub import SportsHub

    hub = SportsHub(db_con=args.db_con)
    query = f"""
        SELECT
            player_id, game_date, season, model_version,
            archetype_0, archetype_1, archetype_2, archetype_3, archetype_4,
            archetype_5, archetype_6, archetype_7, archetype_8, archetype_9
        FROM mod.player_archetype_vw
        WHERE season = '{args.season}'
    """
    return hub.db.read(query).with_columns(pl.col("player_id").cast(pl.Int64))


def ensure_private(db, target: str) -> None:
    """kobe_public reads the view; the base table must stay private."""
    has_role = db.read("SELECT count(*) AS n FROM pg_roles WHERE rolname = 'kobe_public'")[0, "n"]
    if not has_role:
        return
    db.execute(f"REVOKE ALL ON {target} FROM kobe_public")
    granted = db.read(f"SELECT has_table_privilege('kobe_public', '{target}', 'SELECT') AS n")[
        0, "n"
    ]
    if granted:
        raise RuntimeError(f"{target} is still readable by kobe_public")


def create_table(db) -> None:
    target = f"{SCHEMA}.{TABLE}"
    db.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {target} (
            season TEXT,
            game_date DATE NOT NULL,
            game_id INT8 NOT NULL,
            team_id INT8 NOT NULL,
            team_abbreviation TEXT,
            archetype INT8 NOT NULL,
            roster_size INT4,
            expected_starter_weight FLOAT8,
            expected_share FLOAT8,
            actual_starter_share FLOAT8,
            available_share FLOAT8,
            expected_dominant BOOL,
            actual_dominant BOOL,
            top_1_player_id INT8,
            top_1_player_name TEXT,
            top_1_score FLOAT8,
            top_2_player_id INT8,
            top_2_player_name TEXT,
            top_2_score FLOAT8,
            top_3_player_id INT8,
            top_3_player_name TEXT,
            top_3_score FLOAT8,
            model_version TEXT,
            generated_at TIMESTAMPTZ,
            PRIMARY KEY (game_date, game_id, team_id, archetype)
        )
        """
    )
    db.execute(
        f"CREATE INDEX IF NOT EXISTS team_archetype_summary_team_date_idx "
        f"ON {target} (team_id, game_date)"
    )
    db.execute(f"CREATE INDEX IF NOT EXISTS team_archetype_summary_season_idx ON {target} (season)")
    ensure_private(db, target)


def publish(db, summary: pl.DataFrame, season: str) -> None:
    create_table(db)
    target = f"{SCHEMA}.{TABLE}"
    with db.engine.begin() as conn:
        conn.execute(text(f"DELETE FROM {target} WHERE season = :season"), {"season": season})
        summary.write_database(target, conn, if_table_exists="append")
    actual = db.read(f"SELECT count(*) AS n FROM {target} WHERE season = '{season}'")[0, "n"]
    if actual != summary.height:
        raise ValueError(f"published {actual} rows, expected {summary.height}")


def main() -> None:
    args = parse_args()
    from scs_hub import SportsHub

    hub = SportsHub(db_con=args.db_con)
    panel = add_pre_game_state(build_panel())
    panel = panel.filter(pl.col("season") == args.season)
    assignments = load_assignments(args)
    frame = attach_responsibilities(panel, assignments)
    version = assignments["model_version"].max()
    summary = (
        team_archetype_summary(frame)
        .with_columns(
            pl.col("archetype").cast(pl.Int64),
            pl.lit(version).alias("model_version"),
            pl.lit(datetime.now(UTC)).alias("generated_at"),
        )
        .select(
            "season",
            "game_date",
            "game_id",
            "team_id",
            "team_abbreviation",
            "archetype",
            "roster_size",
            "expected_starter_weight",
            "expected_share",
            "actual_starter_share",
            "available_share",
            "expected_dominant",
            "actual_dominant",
            "top_1_player_id",
            "top_1_player_name",
            "top_1_score",
            "top_2_player_id",
            "top_2_player_name",
            "top_2_score",
            "top_3_player_id",
            "top_3_player_name",
            "top_3_score",
            "model_version",
            "generated_at",
        )
    )
    out = Path(args.out) / f"{args.season}.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    summary.write_parquet(out)
    print(f"wrote {summary.height:,} rows to {out}")
    if args.publish:
        publish(hub.db, summary, args.season)
        print(f"published {summary.height:,} rows to {SCHEMA}.{TABLE}")
    (out.parent / f"{args.season}.json").write_text(
        json.dumps(
            {
                "season": args.season,
                "rows": summary.height,
                "games": summary.select("game_date", "game_id", "team_id").unique().height,
                "model_version": summary["model_version"].max(),
                "generated_at": datetime.now(UTC).isoformat(),
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
