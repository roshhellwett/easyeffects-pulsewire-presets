"""
Automated unit and integration tests for ProjectPulsewire Web Server & REST API.
"""

import json
import threading
import time
import urllib.request
import urllib.error
import pytest
from pathlib import Path

from projectpulsewire.web.server import PulsewireServer, find_available_port, start_server
from projectpulsewire.web.api import ApiHandler
from projectpulsewire import presets, irs_handler


@pytest.fixture(scope="module")
def live_server():
    """Starts a live local web server in a daemon thread for integration testing."""
    port = find_available_port(start_port=8900)
    server = PulsewireServer(host="127.0.0.1", port=port)
    server.start(block=False)
    time.sleep(0.4)
    yield f"http://127.0.0.1:{port}"
    server.stop()


def _http_get(url: str):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=5) as response:
        content_type = response.headers.get("Content-Type", "")
        data = response.read()
        return response.status, content_type, data


def _http_post(url: str, payload: dict):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


# ===================================================================
# Unit Tests for ApiHandler directly
# ===================================================================

def test_api_get_status():
    status = ApiHandler.get_status()
    assert "version" in status
    assert "presets_total" in status
    assert status["presets_total"] > 0
    assert "irs_total" in status
    assert status["irs_total"] > 0
    assert "active_source" in status
    assert "distro_family" in status


def test_api_get_presets_filtering():
    # All presets
    all_res = ApiHandler.get_presets({})
    assert len(all_res["presets"]) > 0
    assert "Bass" in all_res["categories"]

    # Category filter
    bass_res = ApiHandler.get_presets({"category": ["Bass"]})
    assert all(p["category"] == "Bass" for p in bass_res["presets"])

    # Search filter
    search_res = ApiHandler.get_presets({"search": ["everyday"]})
    assert len(search_res["presets"]) > 0
    assert any("Everyday" in p["name"] for p in search_res["presets"])


def test_api_get_preset_detail():
    presets_list = presets.get_all_presets()
    first_name = presets_list[0]["name"]

    detail = ApiHandler.get_preset_detail(first_name)
    assert detail is not None
    assert detail["name"] == first_name
    assert "plugins_order" in detail
    assert "raw_data" in detail

    # Unknown preset
    assert ApiHandler.get_preset_detail("NonExistentPreset12345") is None


def test_api_set_preset_source():
    res = ApiHandler.set_preset_source({"source": "legacy"})
    assert res["success"] is True
    assert res["active_source"] == "legacypresets"

    res = ApiHandler.set_preset_source({"source": "modern"})
    assert res["success"] is True
    assert res["active_source"] == "modernpresets"


def test_api_get_irs_filtering():
    all_irs = ApiHandler.get_irs({})
    assert len(all_irs["irs"]) > 0
    assert "Dolby" in all_irs["categories"]

    dolby_res = ApiHandler.get_irs({"category": ["Dolby"]})
    assert all(i["category"] == "Dolby" for i in dolby_res["irs"])

    search_res = ApiHandler.get_irs({"search": ["basswaves"]})
    assert len(search_res["irs"]) > 0


def test_api_get_irs_detail():
    irs_list = irs_handler.get_all_irs()
    first_name = irs_list[0]["name"]

    detail = ApiHandler.get_irs_detail(first_name)
    assert detail is not None
    assert detail["name"] == first_name
    assert "size_formatted" in detail
    assert "use_guide" in detail

    assert ApiHandler.get_irs_detail("NonExistentIRS12345") is None


def test_api_audio_stack():
    stack = ApiHandler.get_audio_stack()
    assert "packages" in stack
    assert len(stack["packages"]) > 0
    assert "distro_family" in stack


def test_api_guide_irs():
    guide = ApiHandler.get_irs_guide()
    assert "title" in guide
    assert len(guide["categories"]) > 0
    assert len(guide["steps"]) > 0


# ===================================================================
# Integration Tests with Live HTTP Server
# ===================================================================

def test_http_serve_static_index(live_server):
    status, ctype, data = _http_get(f"{live_server}/")
    assert status == 200
    assert "text/html" in ctype
    assert b"ProjectPulsewire" in data


def test_http_serve_static_css(live_server):
    status, ctype, data = _http_get(f"{live_server}/static/css/style.css")
    assert status == 200
    assert "text/css" in ctype
    assert b"--bg-app" in data or b"--bg-surface" in data


def test_http_serve_static_js(live_server):
    status, ctype, data = _http_get(f"{live_server}/static/js/app.js")
    assert status == 200
    assert "application/javascript" in ctype or "text/javascript" in ctype
    assert b"ProjectPulsewire" in data


def test_http_serve_static_svg(live_server):
    status, ctype, data = _http_get(f"{live_server}/static/img/logo.svg")
    assert status == 200
    assert "image/svg+xml" in ctype
    assert b"<svg" in data


def test_http_api_status_endpoint(live_server):
    status, ctype, data = _http_get(f"{live_server}/api/status")
    assert status == 200
    assert "application/json" in ctype
    res = json.loads(data.decode("utf-8"))
    assert res["presets_total"] > 0


def test_http_api_presets_endpoint(live_server):
    status, ctype, data = _http_get(f"{live_server}/api/presets?category=Bass")
    assert status == 200
    res = json.loads(data.decode("utf-8"))
    assert len(res["presets"]) > 0
    assert all(p["category"] == "Bass" for p in res["presets"])


def test_http_api_preset_detail_endpoint(live_server):
    all_presets = presets.get_all_presets()
    p_name = urllib.parse.quote(all_presets[0]["name"])
    status, ctype, data = _http_get(f"{live_server}/api/presets/{p_name}")
    assert status == 200
    res = json.loads(data.decode("utf-8"))
    assert res["name"] == all_presets[0]["name"]


def test_http_api_preset_install_and_remove(live_server, monkeypatch, tmp_path):
    home = tmp_path / "home"
    native_output = home / ".config" / "easyeffects" / "output"
    native_output.mkdir(parents=True)
    monkeypatch.setattr(presets, "_get_real_home", lambda: home)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    presets._clear_cache()

    all_presets = presets.get_all_presets()
    target_preset = all_presets[0]["name"]

    # Install
    code, res = _http_post(f"{live_server}/api/presets/install", {"name": target_preset})
    assert code == 200
    assert res["success"] is True
    assert presets.is_preset_installed(target_preset)

    # Remove
    code, res = _http_post(f"{live_server}/api/presets/remove", {"name": target_preset})
    assert code == 200
    assert res["success"] is True
    assert not presets.is_preset_installed(target_preset)


def test_http_api_irs_install_and_remove(live_server, monkeypatch, tmp_path):
    home = tmp_path / "home"
    native_irs = home / ".config" / "easyeffects" / "irs"
    native_irs.mkdir(parents=True)
    monkeypatch.setattr(irs_handler, "_get_real_home", lambda: home)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    irs_handler._clear_cache()

    all_irs = irs_handler.get_all_irs()
    target_irs = all_irs[0]["name"]

    # Install
    code, res = _http_post(f"{live_server}/api/irs/install", {"name": target_irs})
    assert code == 200
    assert res["success"] is True
    assert irs_handler.is_irs_installed(target_irs)

    # Remove
    code, res = _http_post(f"{live_server}/api/irs/remove", {"name": target_irs})
    assert code == 200
    assert res["success"] is True
    assert not irs_handler.is_irs_installed(target_irs)
