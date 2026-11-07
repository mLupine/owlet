"""Load checked-in synthetic fixtures without the HA Core namespace."""

from pathlib import Path


def load_fixture(name: str, integration: str = "owlet") -> str:
    return (Path(__file__).parent / "fixtures" / name).read_text()
