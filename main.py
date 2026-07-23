"""KnowledgeTree の起動エントリーポイント。"""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from knowledge_tree.application import run


if __name__ == "__main__":
    raise SystemExit(run())
