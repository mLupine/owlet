"""Build deterministic flat HACS and optional-example archives."""

import json
from hashlib import sha256
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]


def write_archive(destination: Path, files: list[tuple[Path, str]]) -> str:
    with ZipFile(destination, "w", compression=ZIP_DEFLATED) as archive:
        for source, name in sorted(files, key=lambda item: item[1]):
            info = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.external_attr = 0o644 << 16
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, source.read_bytes())
    return sha256(destination.read_bytes()).hexdigest()


def build_release() -> None:
    component = ROOT / "custom_components" / "owlet"
    manifest = json.loads((component / "manifest.json").read_text())
    assert manifest["domain"] == "owlet" and manifest["version"]
    destination = ROOT / "dist"
    destination.mkdir(exist_ok=True)
    files = [
        (path, path.relative_to(component).as_posix())
        for path in component.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    ]
    package_hash = write_archive(destination / "owlet.zip", files)
    with ZipFile(destination / "owlet.zip") as archive:
        assert {
            "manifest.json",
            "__init__.py",
            "switch.py",
            "LICENSE",
            "NOTICE",
            "owletapi/LICENSE",
            "icons.json",
            "translations/nl.json",
            "translations/en.json",
            "translations/fr.json",
            "translations/uk.json",
        } <= set(archive.namelist())
        assert not any(
            name.startswith("custom_components/") or "__pycache__" in name
            for name in archive.namelist()
        )
        assert archive.testzip() is None
    examples = [
        (path, path.relative_to(ROOT).as_posix())
        for folder in ("blueprints", "dashboards")
        for path in (ROOT / folder).rglob("*.yaml")
    ]
    examples.append((ROOT / "NOTICE", "NOTICE"))
    example_hash = write_archive(destination / "owlet-examples.zip", examples)
    (destination / "SHA256SUMS").write_text(
        f"{package_hash}  owlet.zip\n{example_hash}  owlet-examples.zip\n"
    )
    print((destination / "SHA256SUMS").read_text(), end="")


if __name__ == "__main__":
    build_release()
