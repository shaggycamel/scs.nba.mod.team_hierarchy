"""Persist and load the fitted hierarchy models.

A bundle holds the four fitted models and the feature lists they were trained
with. `load` refuses a library-version mismatch unless `strict=False`.
"""

from __future__ import annotations

import json
import pickle
import platform
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

BUNDLE_VERSION = 1
CHECKED_PACKAGES = ("scikit-learn", "lightgbm", "numpy", "polars")


@dataclass
class HierarchyBundle:
    position_model: object
    play_model: object
    minutes_model: object
    usage_model: object
    features: dict[str, list[str]]
    metadata: dict


def package_versions() -> dict[str, str]:
    out = {}
    for name in CHECKED_PACKAGES:
        try:
            out[name] = version(name)
        except PackageNotFoundError:
            out[name] = "not installed"
    return out


def build_metadata(
    *,
    trained_through: str,
    cutoff: str,
    seasons: list[str],
    rows: int,
    features: dict[str, list[str]],
    git_commit: str | None = None,
) -> dict:
    return {
        "bundle_version": BUNDLE_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "trained_through": trained_through,
        "cutoff": cutoff,
        "seasons": seasons,
        "rows": rows,
        "features": features,
        "packages": package_versions(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "git_commit": git_commit,
    }


def save(bundle: HierarchyBundle, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "wb") as fh:
        pickle.dump(bundle, fh, protocol=pickle.HIGHEST_PROTOCOL)
    tmp.replace(path)
    path.with_name("model.json").write_text(json.dumps(bundle.metadata, indent=2) + "\n")
    return path


def load(path: Path, strict: bool = True) -> HierarchyBundle:
    with open(path, "rb") as fh:
        bundle = pickle.load(fh)
    if not isinstance(bundle, HierarchyBundle):
        raise TypeError(f"{path} is not a HierarchyBundle")
    if bundle.metadata.get("bundle_version") != BUNDLE_VERSION:
        raise ValueError(
            f"{path}: bundle version {bundle.metadata.get('bundle_version')} != {BUNDLE_VERSION}"
        )
    trained = bundle.metadata.get("packages", {})
    current = package_versions()
    mismatched = {
        name: (trained.get(name), current.get(name))
        for name in CHECKED_PACKAGES
        if trained.get(name) != current.get(name)
    }
    if mismatched and strict:
        detail = ", ".join(f"{k}: {a} -> {b}" for k, (a, b) in mismatched.items())
        raise RuntimeError(
            "model was fitted with different library versions "
            f"({detail}); reinstate them or load with strict=False"
        )
    return bundle
