"""A fresh judge checkout can replay evidence without contaminating colony metrics."""
import json

from hivelens import config, store, workspace
from hivelens.example import EXAMPLE_DIR, install_if_empty
import server


def test_example_is_offline_idempotent_and_not_live_status(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "HIVES_DIR", tmp_path / "hives")
    with workspace.scope("production"):
        assert install_if_empty()
        assert workspace.current() == "production"
        assert store.list_hives() == []
    hive = store.list_hives()[0]
    record = store.inspections(hive["id"])[0]
    original = json.loads((EXAMPLE_DIR / "inspection.json").read_text())
    assert record == original
    for name in record["files"].values():
        assert store.file_path(hive["id"], record["id"], name).is_file()
    assert not install_if_empty()
    assert len(store.list_hives()) == 1
    assert store.history_before(hive["id"], "2099-01-01") == []
    assert store.metrics_rows(hive["id"]) == []
    node = server.build_apiary_overview()["hives"][0]
    assert node["overall"] == "unknown"
    assert node["inspection_count"] == 0
    assert node["sample_inspection_count"] == 1


def test_example_preserves_existing_workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "HIVES_DIR", tmp_path / "hives")
    hive = store.create_hive("My hive")
    assert not install_if_empty()
    assert store.list_hives() == [hive]


def test_fresh_volume_offers_attributed_samples_for_new_analysis(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(server, '_SAMPLE_CACHE', None)
    samples = server.get_samples()
    assert samples['boards'][0]['name'] == 'IMG_5582.jpg'
    assert samples['boards'][0]['experts'] == 21
    assert samples['frames'][0]['path'].endswith('frame_1.jpg')
