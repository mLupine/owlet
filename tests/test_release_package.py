"""Deterministic packages match the exact allowed candidate source."""

import json
import shutil
from zipfile import ZipFile

import pytest

from scripts.build_release import (
    ROOT,
    build_release,
    component_files,
    validate_manifest,
    verify_source_archive,
)


@pytest.fixture
def candidate(tmp_path):
    component = tmp_path / "custom_components" / "owlet"
    shutil.copytree(
        ROOT / "custom_components" / "owlet",
        component,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    for folder in ("blueprints", "dashboards"):
        shutil.copytree(ROOT / folder, tmp_path / folder)
    shutil.copy(ROOT / "NOTICE", tmp_path / "NOTICE")
    return tmp_path


def test_packages_are_identical_across_builds_and_match_source(candidate):
    build_release(candidate)
    first = {path.name: path.read_bytes() for path in (candidate / "dist").iterdir()}
    build_release(candidate)
    assert first == {
        path.name: path.read_bytes() for path in (candidate / "dist").iterdir()
    }
    with ZipFile(candidate / "dist/owlet.zip") as archive:
        for path, name in component_files(candidate / "custom_components/owlet"):
            assert archive.read(name) == path.read_bytes()
        assert archive.read("brand/icon.png").startswith(b"\x89PNG\r\n\x1a\n")
        assert b"Ryan" in archive.read("NOTICE")


@pytest.mark.parametrize("change", ["extra", "missing", "symlink"])
def test_package_refuses_unreviewed_inventory(candidate, change):
    component = candidate / "custom_components/owlet"
    if change == "extra":
        (component / "household-secret.json").write_text("synthetic")
    elif change == "missing":
        (component / "brand/icon.png").unlink()
    else:
        (component / "strings.json").unlink()
        (component / "strings.json").symlink_to(
            ROOT / "custom_components/owlet/strings.json"
        )
    with pytest.raises(ValueError, match="inventory"):
        build_release(candidate)


@pytest.mark.parametrize("version", ["2026.13.0", "2026.0.1", "2026.11", "garbage"])
def test_package_refuses_invalid_version(candidate, version):
    component = candidate / "custom_components/owlet"
    path = component / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["version"] = version
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="version"):
        validate_manifest(component)


def test_tag_and_runtime_requirements_match_candidate(candidate):
    component = candidate / "custom_components/owlet"
    version = json.loads((component / "manifest.json").read_text())["version"]
    assert validate_manifest(component, f"v{version}")["version"] == version
    with pytest.raises(ValueError, match="tag"):
        validate_manifest(component, "2020.1.0")
    manifest = json.loads((component / "manifest.json").read_text())
    manifest["requirements"] = ["unreviewed==1.0"]
    (component / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="requirements"):
        build_release(candidate)


@pytest.mark.parametrize("changed", [False, True])
def test_source_zip_installation_bytes_match_candidate(candidate, changed):
    component = candidate / "custom_components/owlet"
    source = candidate / "source.zip"
    with ZipFile(source, "w") as archive:
        for path, name in component_files(component):
            archive.writestr(
                f"owlet-candidate/custom_components/owlet/{name}", path.read_bytes()
            )
        archive.writestr("owlet-candidate/tests/household-excluded.json", "synthetic")
    if changed:
        (component / "const.py").write_text("different source")
        with pytest.raises(ValueError, match="differs"):
            verify_source_archive(source, component)
    else:
        build_release(candidate, source_archive=source)
