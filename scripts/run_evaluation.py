"""One-command Wave 2 evaluation run. See amis/evaluation/runner.py.

Run with: python scripts/run_evaluation.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from amis.evaluation.runner import main

if __name__ == "__main__":
    sys.exit(main())
