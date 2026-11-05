import pytest


@pytest.fixture(autouse=True)
def no_photo_check_calls(monkeypatch, request):
    """Tests never call the model to classify photos; test_photo_check covers the check itself."""
    if request.module.__name__.endswith("test_photo_check"):
        return
    from hivelens import photo_check
    monkeypatch.setattr(photo_check, "classify", lambda image: None)
