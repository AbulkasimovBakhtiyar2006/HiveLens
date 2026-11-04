"""Install an attributed, saved model run in a fresh demo workspace. No API calls."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from . import store, workspace

EXAMPLE_DIR = Path(__file__).parent / "examples" / "photo-analysis"


def install_if_empty() -> bool:
    """Never replace existing demo data or populate the production workspace."""
    with workspace.scope("demo"):
        if store.list_hives() or store.list_farms():
            return False
        record = json.loads((EXAMPLE_DIR / "inspection.json").read_text())
        farm = store.create_farm("Public photo examples", "Unrelated sample photographs")
        hive = store.create_hive("Saved photo analysis", "Public samples · not a field colony", farm["id"])
        target = workspace.hives_dir() / hive["id"] / record["id"]
        shutil.copytree(EXAMPLE_DIR, target)
        return True
