from __future__ import annotations

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from arxiv_digest.category_utils import category_pattern_matches, matches_any_category_pattern


class CategoryUtilsTests(unittest.TestCase):
    def test_wildcard_pattern(self) -> None:
        self.assertTrue(category_pattern_matches("cs.*", "cs.AI"))
        self.assertTrue(category_pattern_matches("cs.*", "cs.CV"))
        self.assertFalse(category_pattern_matches("cs.*", "stat.ML"))

    def test_exact_pattern(self) -> None:
        self.assertTrue(category_pattern_matches("cs.AI", "cs.AI"))
        self.assertFalse(category_pattern_matches("cs.AI", "cs.CV"))

    def test_matches_any(self) -> None:
        patterns = ["stat.ML", "cs.*"]
        self.assertTrue(matches_any_category_pattern(patterns, "cs.RO"))
        self.assertTrue(matches_any_category_pattern(patterns, "stat.ML"))
        self.assertFalse(matches_any_category_pattern(patterns, "math.OC"))


if __name__ == "__main__":
    unittest.main()

