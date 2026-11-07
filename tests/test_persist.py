from __future__ import annotations

import pytest

from team_hierarchy import persist


def _bundle() -> persist.HierarchyBundle:
    features = {"position": ["a"], "play": ["b"], "absorption": ["c"]}
    metadata = persist.build_metadata(
        trained_through="2025-26",
        cutoff="2026-06-13",
        seasons=["2025-26"],
        rows=1,
        features=features,
    )
    return persist.HierarchyBundle(
        position_model={"model": "position"},
        play_model={"model": "play"},
        minutes_model={"model": "minutes"},
        usage_model={"model": "usage"},
        features=features,
        metadata=metadata,
    )


def test_bundle_round_trip(tmp_path):
    path = persist.save(_bundle(), tmp_path / "model.pkl")
    loaded = persist.load(path)
    assert loaded.metadata["trained_through"] == "2025-26"
    assert loaded.position_model == {"model": "position"}
    assert (tmp_path / "model.json").exists()


def test_version_mismatch_is_loud(tmp_path):
    bundle = _bundle()
    bundle.metadata["packages"]["lightgbm"] = "0.0.0"
    path = persist.save(bundle, tmp_path / "model.pkl")
    with pytest.raises(RuntimeError, match="different library versions"):
        persist.load(path)
    assert persist.load(path, strict=False).metadata["packages"]["lightgbm"] == "0.0.0"
