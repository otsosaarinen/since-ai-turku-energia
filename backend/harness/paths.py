"""Where things live on disk, so no module builds relative paths of its own."""

from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = HARNESS_DIR.parent
REPO_ROOT = BACKEND_DIR.parent
REPORTS_DIR = HARNESS_DIR / "reports"  # git-ignored: answers, memory.json and fetched data
FETCHED_DATA_DIR = REPORTS_DIR / "data"
