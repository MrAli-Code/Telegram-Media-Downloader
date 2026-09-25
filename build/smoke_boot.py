import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from app import main  # noqa: E402

try:
    sys.exit(main())
except SystemExit as exc:
    sys.exit(exc.code)