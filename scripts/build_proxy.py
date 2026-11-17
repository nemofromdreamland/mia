"""Build build/proxy.zip for the Lambda proxy (task 4.2).

The zip carries `proxy/` plus a pinned boto3: the Lambda runtime's own boto3 may not
know the `bedrock-agentcore` service yet. boto3 is pure Python, so the zip runs on arm64.

Usage: uv run python scripts/build_proxy.py
"""

import shutil
import subprocess
import tempfile
import zipfile
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "build" / "proxy.zip"
BOTO_VERSION = "1.44.3"  # same as uv.lock (tests/test_build_proxy.py checks it)


def install_boto(target: Path) -> None:
    """Install boto3/botocore into `target` with uv."""
    subprocess.run(
        [
            "uv", "pip", "install", "--quiet", "--target", str(target),
            f"boto3=={BOTO_VERSION}", f"botocore=={BOTO_VERSION}",
        ],
        check=True,
    )  # fmt: skip


def build_zip(dest: Path = DEST, install: Callable[[Path], None] = install_boto) -> Path:
    """Zip `proxy/*.py` and the installed packages into `dest` (replaced if present)."""
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp)
        install(stage)
        shutil.copytree(
            ROOT / "proxy", stage / "proxy", ignore=shutil.ignore_patterns("__pycache__")
        )
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.unlink(missing_ok=True)
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(stage.rglob("*")):
                if path.is_file() and "__pycache__" not in path.parts:
                    archive.write(path, path.relative_to(stage).as_posix())
    return dest


def main() -> None:
    print(f"OK: {build_zip()}")


if __name__ == "__main__":
    main()
