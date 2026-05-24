import importlib
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


class ImportBoundaryTests(unittest.TestCase):
    def test_bot_and_handover_flow_import_without_circular_dependency(self):
        importlib.import_module("src.bot")
        importlib.import_module("src.handover_flow")


if __name__ == "__main__":
    unittest.main()
