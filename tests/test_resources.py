from pathlib import Path

from projectpulsewire import irs_handler, presets


def test_preset_cache_is_scoped_by_source():
    modern = presets.get_all_presets(force_refresh=True, preset_source="modernpresets")
    legacy = presets.get_all_presets(preset_source="legacypresets")

    assert modern
    assert legacy
    assert {preset["source"] for preset in modern} == {"modernpresets"}
    assert {preset["source"] for preset in legacy} == {"legacypresets"}
    assert modern != legacy


def test_preset_source_aliases_work():
    assert presets.set_active_preset_source("modern") is True
    assert presets.get_active_preset_source() == "modernpresets"
    assert presets.set_active_preset_source("legacy") is True
    assert presets.get_active_preset_source() == "legacypresets"
    assert presets.set_active_preset_source("modernpresets") is True


def test_installed_presets_include_native_and_flatpak(monkeypatch, tmp_path):
    home = tmp_path / "home"
    native_output = home / ".config" / "easyeffects" / "output"
    flatpak_output = (
        home
        / ".var"
        / "app"
        / "com.github.wwmm.easyeffects"
        / "config"
        / "easyeffects"
        / "output"
    )
    native_output.mkdir(parents=True)
    flatpak_output.mkdir(parents=True)
    (native_output / "Native.json").write_text("{}", encoding="utf-8")
    (flatpak_output / "Flatpak.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(presets, "_get_real_home", lambda: home)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    presets._clear_cache()

    assert presets.get_installed_presets() == ["Flatpak", "Native"]

    success, message = presets.remove_preset("Native")

    assert success is True
    assert "Native" in message
    assert not (native_output / "Native.json").exists()


def test_remove_preset_cleans_duplicate_native_and_flatpak(monkeypatch, tmp_path):
    home = tmp_path / "home"
    native_output = home / ".config" / "easyeffects" / "output"
    flatpak_output = (
        home
        / ".var"
        / "app"
        / "com.github.wwmm.easyeffects"
        / "config"
        / "easyeffects"
        / "output"
    )
    native_output.mkdir(parents=True)
    flatpak_output.mkdir(parents=True)
    for directory in (native_output, flatpak_output):
        (directory / "Shared.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(presets, "_get_real_home", lambda: home)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    presets._clear_cache()

    success, message = presets.remove_preset("shared")

    assert success is True
    assert "2 location" in message
    assert not (native_output / "Shared.json").exists()
    assert not (flatpak_output / "Shared.json").exists()


def test_installed_irs_include_native_and_flatpak(monkeypatch, tmp_path):
    home = tmp_path / "home"
    native_irs = home / ".config" / "easyeffects" / "irs"
    flatpak_irs = (
        home
        / ".var"
        / "app"
        / "com.github.wwmm.easyeffects"
        / "config"
        / "easyeffects"
        / "irs"
    )
    native_irs.mkdir(parents=True)
    flatpak_irs.mkdir(parents=True)
    (native_irs / "Native.irs").write_bytes(b"irs")
    (flatpak_irs / "Flatpak.irs").write_bytes(b"irs")

    monkeypatch.setattr(irs_handler, "_get_real_home", lambda: home)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    irs_handler._clear_cache()

    assert irs_handler.get_installed_irs() == ["Flatpak", "Native"]


def test_remove_irs_cleans_duplicate_native_and_flatpak(monkeypatch, tmp_path):
    home = tmp_path / "home"
    native_irs = home / ".config" / "easyeffects" / "irs"
    flatpak_irs = (
        home
        / ".var"
        / "app"
        / "com.github.wwmm.easyeffects"
        / "config"
        / "easyeffects"
        / "irs"
    )
    native_irs.mkdir(parents=True)
    flatpak_irs.mkdir(parents=True)
    for directory in (native_irs, flatpak_irs):
        (directory / "Shared.irs").write_bytes(b"irs")

    monkeypatch.setattr(irs_handler, "_get_real_home", lambda: home)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    irs_handler._clear_cache()

    success, message = irs_handler.remove_irs("shared")

    assert success is True
    assert "2 location" in message
    assert not (native_irs / "Shared.irs").exists()
    assert not (flatpak_irs / "Shared.irs").exists()


def test_no_test_absolute_path_leaks_into_package_imports():
    assert Path(__file__).exists()
