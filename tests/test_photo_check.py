"""Photos that are not a sticky board or a hive frame are refused before analysis."""
import pytest
from PIL import Image

from hivelens import measure, photo_check, sam


def test_unrelated_photo_is_refused_with_a_clear_message(monkeypatch):
    monkeypatch.setattr(photo_check, "classify", lambda image: {"kind": "other", "why": "a cat on a sofa"})
    with pytest.raises(photo_check.NotHivePhoto, match="does not look like a beehive frame.*a cat on a sofa"):
        photo_check.require(Image.new("RGB", (8, 8)), "hive_frame", "frame photo 1")


def test_board_in_the_frame_slot_points_to_the_right_section(monkeypatch):
    monkeypatch.setattr(photo_check, "classify", lambda image: {"kind": "sticky_board", "why": ""})
    with pytest.raises(photo_check.NotHivePhoto, match="Sticky board section"):
        photo_check.require(Image.new("RGB", (8, 8)), "hive_frame", "frame photo 1")


def test_matching_photo_and_unavailable_check_both_go_ahead(monkeypatch):
    monkeypatch.setattr(photo_check, "classify", lambda image: {"kind": "sticky_board", "why": ""})
    photo_check.require(Image.new("RGB", (8, 8)), "sticky_board", "sticky-board photo")
    monkeypatch.setattr(photo_check, "classify", lambda image: None)  # model error: fail open
    photo_check.require(Image.new("RGB", (8, 8)), "sticky_board", "sticky-board photo")


def test_model_errors_fail_open(monkeypatch, tmp_path):
    from hivelens import config
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)

    def broken():
        raise RuntimeError("network down")

    monkeypatch.setattr(photo_check, "client", broken)
    assert photo_check.classify(Image.new("RGB", (8, 8))) is None


def test_frame_without_any_comb_stops_before_muse(monkeypatch):
    monkeypatch.setattr(sam, "segment", lambda *a, **k: [])
    with pytest.raises(photo_check.NotHivePhoto, match="no honeycomb"):
        measure.measure_comb(Image.new("RGB", (64, 64)))
