"""Packaging of the Lambda proxy (task 4.2): zip layout and pinned boto3."""

import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build_proxy  # noqa: E402


def fake_install(target: Path) -> None:
    (target / "boto3").mkdir(parents=True)
    (target / "boto3" / "__init__.py").write_text("", encoding="utf-8")
    (target / "boto3" / "__pycache__").mkdir()
    (target / "boto3" / "__pycache__" / "x.pyc").write_bytes(b"")


def test_zip_has_proxy_and_boto(tmp_path: Path) -> None:
    dest = build_proxy.build_zip(tmp_path / "proxy.zip", install=fake_install)
    names = set(zipfile.ZipFile(dest).namelist())
    assert {"proxy/__init__.py", "proxy/handler.py", "boto3/__init__.py"} <= names
    assert not [name for name in names if "__pycache__" in name]


def test_rebuild_replaces_old_zip(tmp_path: Path) -> None:
    dest = tmp_path / "proxy.zip"
    dest.write_bytes(b"old")
    build_proxy.build_zip(dest, install=fake_install)
    assert zipfile.is_zipfile(dest)


def test_boto_version_matches_lock() -> None:
    lock = (ROOT / "uv.lock").read_text(encoding="utf-8")
    locked = re.search(r'name = "boto3"\nversion = "([^"]+)"', lock)
    assert locked and build_proxy.BOTO_VERSION == locked.group(1)
