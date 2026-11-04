"""HiveLens: hive inspection agent built on Meta's SAM 3.1 and Muse Spark."""

import sys

__version__ = "0.1.0-beta"

if sys.version_info < (3, 10):
    raise RuntimeError(
        f"HiveLens needs Python 3.10+ (Meta's meta-sam-parser requires it); this is {sys.version.split()[0]}. "
        "Quick fix: `uv venv --python 3.12 && source .venv/bin/activate && uv pip install -r requirements.txt`."
    )
