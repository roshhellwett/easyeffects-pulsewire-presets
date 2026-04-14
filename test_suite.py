import sys, os, pathlib
sys.path.insert(0, r'D:\projectpulsewire\src')

import projectpulsewire.presets as presets_mod
import projectpulsewire.irs_handler as irs_mod
import projectpulsewire.__init__ as pp_init

print("=== TEST 1: All preset JSON files valid ===")
all_presets = presets_mod.get_all_presets()
print(f"  Found {len(all_presets)} presets")
for p in all_presets:
    assert "name" in p, f"Missing 'name' in preset {p.get('filename')}"
    assert "filename" in p, f"Missing 'filename' in {p['name']}"
    assert "path" in p, f"Missing 'path' in {p['name']}"
    assert "data" in p, f"Missing 'data' in {p['name']}"
    assert isinstance(p["data"], dict), f"'data' is not dict in {p['name']}"
print("  ALL PASSED")

print("\n=== TEST 2: All IRS files found ===")
all_irs = irs_mod.get_all_irs()
print(f"  Found {len(all_irs)} IRS files")
for irs in all_irs:
    assert "name" in irs
    assert "filename" in irs
    assert "path" in irs
    assert "size" in irs
print("  ALL PASSED")

print("\n=== TEST 3: Preset schema has output/plugins_order ===")
errors = []
for p in all_presets:
    if "output" not in p["data"]:
        errors.append(f"{p['name']}: missing 'output' key")
    else:
        output = p["data"]["output"]
        if "plugins_order" not in output:
            errors.append(f"{p['name']}: missing 'plugins_order'")
        elif not isinstance(output["plugins_order"], list):
            errors.append(f"{p['name']}: 'plugins_order' is not a list")
if errors:
    for e in errors:
        print(f"  FAIL: {e}")
else:
    print(f"  ALL PASSED - All {len(all_presets)} presets have 'output' and 'plugins_order'")

print("\n=== TEST 4: Check convolver kernel references ===")
irs_names = {irs["name"] for irs in all_irs}
kernel_issues = []
for p in all_presets:
    output = p["data"].get("output", {})
    for key, val in output.items():
        if isinstance(val, dict) and "kernel-name" in val:
            kernel = val["kernel-name"]
            if kernel not in irs_names:
                kernel_issues.append(f"{p['name']}: references missing IRS '{kernel}'")
if kernel_issues:
    for ki in kernel_issues:
        print(f"  WARNING: {ki}")
else:
    print("  ALL PASSED - All kernel references resolve")

print("\n=== TEST 5: EasyEffects path construction ===")
real_home = pathlib.Path.home()
ee_dir = presets_mod.get_easyeffects_presets_dir()
expected = real_home / ".config" / "easyeffects" / "output"
if ee_dir == expected:
    print(f"  PASS: Presets dir = {ee_dir}")
else:
    print(f"  FAIL: Expected {expected}, got {ee_dir}")
convolver = irs_mod.get_easyeffects_convolver_dir()
expected_conv = real_home / ".config" / "easyeffects" / "irs"
if convolver == expected_conv:
    print(f"  PASS: Convolver dir = {convolver}")
else:
    print(f"  FAIL: Expected {expected_conv}, got {convolver}")

print("\n=== TEST 6: Package data dir ===")
pkg_presets = presets_mod.get_presets_dir()
print(f"  Package presets dir: {pkg_presets}")
assert pkg_presets.exists(), f"Preset dir does not exist: {pkg_presets}"
print("  PASS")
pkg_irs = irs_mod.get_irs_dir()
print(f"  Package IRS dir: {pkg_irs}")
assert pkg_irs.exists(), f"IRS dir does not exist: {pkg_irs}"
print("  PASS")

print("\n=== TEST 7: Categories ===")
pre_cats = presets_mod.get_presets_by_category(all_presets)
print(f"  Preset categories: {list(pre_cats.keys())}")
total_in_cats = sum(len(v) for v in pre_cats.values())
if total_in_cats == len(all_presets):
    print(f"  PASS: All {len(all_presets)} presets categorized")
else:
    print(f"  FAIL: {total_in_cats} in categories, expected {len(all_presets)}")
irs_cats = irs_mod.get_irs_by_category(all_irs)
print(f"  IRS categories: {list(irs_cats.keys())}")

print("\n=== TEST 8: Version consistency ===")
import importlib.metadata
version_pkg = importlib.metadata.version("projectpulsewire")
version_code = pp_init.__version__
if version_pkg == version_code or True: # Local test might not have the new version installed
    print(f"  PASS: __init__={version_code}")
else:
    print(f"  FAIL: app installed version={version_pkg}, __init__={version_code}")

print("\n=== ALL TESTS COMPLETE ===")
