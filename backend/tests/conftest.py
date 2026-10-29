import pytest
from app import JD_CACHE


@pytest.fixture(autouse=True)
def _isolated_profile_store(tmp_path, monkeypatch):
    """Keep profile, JD and content-cache test data out of backend/data/."""
    monkeypatch.setenv("PROFILE_STORE_DIR", str(tmp_path / "profiles"))
    monkeypatch.setenv("JD_STORE_DIR", str(tmp_path / "jds"))
    # app.py constructs JD_CACHE at import time, so patch the existing object too.
    monkeypatch.setattr(JD_CACHE, "path", tmp_path / "jd-cache.json")
