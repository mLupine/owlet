"""Build deterministic flat HACS and optional-example archives."""

import argparse
import json
import re
from hashlib import sha256
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]

COMPONENT_FILES = frozenset(
    (
        "LICENSE",
        "NOTICE",
        "__init__.py",
        "binary_sensor.py",
        "brand/SOURCE.txt",
        "brand/icon.png",
        "brand/icon@2x.png",
        "brand/logo.png",
        "brand/logo@2x.png",
        "config_flow.py",
        "const.py",
        "coordinator.py",
        "diagnostics.py",
        "entity.py",
        "icons.json",
        "manifest.json",
        "owletapi/LICENSE",
        "owletapi/__init__.py",
        "owletapi/api.py",
        "owletapi/const.py",
        "owletapi/exceptions.py",
        "owletapi/sock.py",
        "sensor.py",
        "sleep_data.py",
        "strings.json",
        "switch.py",
        "translations/en.json",
        "translations/fr.json",
        "translations/nl.json",
        "translations/uk.json",
    )
)


def write_archive(destination: Path, files: list[tuple[Path, str]]) -> str:
    with ZipFile(destination, "w", compression=ZIP_DEFLATED) as archive:
        for source, name in sorted(files, key=lambda item: item[1]):
            info = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.external_attr = 0o644 << 16
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, source.read_bytes())
    return sha256(destination.read_bytes()).hexdigest()


def component_files(component: Path) -> list[tuple[Path, str]]:
    files = [
        (path, path.relative_to(component).as_posix())
        for path in component.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    ]
    actual = {name for _, name in files}
    if actual != COMPONENT_FILES or any(path.is_symlink() for path, _ in files):
        raise ValueError(
            f"Unexpected component inventory: missing={sorted(COMPONENT_FILES - actual)}, extra={sorted(actual - COMPONENT_FILES)}"
        )
    return files


def validate_manifest(component: Path, tag: str | None = None) -> dict:
    manifest = json.loads((component / "manifest.json").read_text())
    version = manifest.get("version", "")
    if manifest.get("domain") != "owlet" or not re.fullmatch(
        r"[0-9]{4}\.(?:[1-9]|1[0-2])\.[0-9]+(?:(?:a|b|rc)[0-9]+)?", version
    ):
        raise ValueError("Invalid Owlet manifest domain or calendar version")
    if tag is not None and tag.removeprefix("v") != version:
        raise ValueError("Release tag differs from manifest version")
    if manifest.get("requirements") != []:
        raise ValueError("Bundled client must not add external runtime requirements")
    return manifest


def verify_source_archive(source: Path, component: Path) -> None:
    """Compare a GitHub-style source ZIP's installed files with the candidate."""
    expected = {name: path.read_bytes() for path, name in component_files(component)}
    marker = "custom_components/owlet/"
    with ZipFile(source) as archive:
        actual = {}
        for info in archive.infolist():
            if info.is_dir() or marker not in info.filename:
                continue
            name = info.filename.split(marker, 1)[1]
            if name in actual:
                raise ValueError("Duplicate source archive member")
            actual[name] = archive.read(info)
        if actual != expected:
            raise ValueError("Source archive differs from candidate component")


def build_release(
    root: Path = ROOT, tag: str | None = None, source_archive: Path | None = None
) -> None:
    component = root / "custom_components" / "owlet"
    validate_manifest(component, tag)
    files = component_files(component)
    if source_archive is not None:
        verify_source_archive(source_archive, component)
    destination = root / "dist"
    destination.mkdir(exist_ok=True)
    package_hash = write_archive(destination / "owlet.zip", files)
    with ZipFile(destination / "owlet.zip") as archive:
        if (
            set(archive.namelist()) != COMPONENT_FILES
            or any(archive.read(name) != source.read_bytes() for source, name in files)
            or archive.testzip() is not None
        ):
            raise ValueError("Built archive differs from source")
    examples = [
        (path, path.relative_to(root).as_posix())
        for folder in ("blueprints", "dashboards")
        for path in (root / folder).rglob("*.yaml")
    ]
    examples.append((root / "NOTICE", "NOTICE"))
    example_hash = write_archive(destination / "owlet-examples.zip", examples)
    (destination / "SHA256SUMS").write_text(
        f"{package_hash}  owlet.zip\n{example_hash}  owlet-examples.zip\n"
    )
    print((destination / "SHA256SUMS").read_text(), end="")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag")
    parser.add_argument("--source-archive", type=Path)
    arguments = parser.parse_args()
    build_release(tag=arguments.tag, source_archive=arguments.source_archive)
