from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from arxiv_digest.time_utils import current_day_cutoff_utc, latest_arxiv_announcement_cutoff_utc


class TimeUtilsTests(unittest.TestCase):
    def test_current_day_cutoff_utc_chicago(self) -> None:
        now_utc = datetime(2026, 3, 13, 18, 30, tzinfo=timezone.utc)
        cutoff = current_day_cutoff_utc("America/Chicago", now_utc=now_utc)
        # Midnight in Chicago on 2026-03-13 corresponds to 05:00 UTC (CDT, UTC-5).
        self.assertEqual(cutoff, datetime(2026, 3, 13, 5, 0, tzinfo=timezone.utc))

    def test_invalid_timezone_falls_back_to_utc(self) -> None:
        now_utc = datetime(2026, 3, 13, 18, 30, tzinfo=timezone.utc)
        cutoff = current_day_cutoff_utc("Invalid/Timezone", now_utc=now_utc)
        self.assertEqual(cutoff, datetime(2026, 3, 13, 0, 0, tzinfo=timezone.utc))

    def test_latest_arxiv_announcement_cutoff_on_friday(self) -> None:
        # Friday 18:30 UTC is before any next announcement; latest is Thursday 20:00 ET.
        now_utc = datetime(2026, 3, 13, 18, 30, tzinfo=timezone.utc)
        cutoff = latest_arxiv_announcement_cutoff_utc(now_utc=now_utc)
        self.assertEqual(cutoff, datetime(2026, 3, 13, 0, 0, tzinfo=timezone.utc))

    def test_latest_arxiv_announcement_cutoff_on_sunday_before_release(self) -> None:
        # Sunday before 20:00 ET should still point to Thursday 20:00 ET release.
        now_utc = datetime(2026, 3, 15, 17, 0, tzinfo=timezone.utc)  # 13:00 ET
        cutoff = latest_arxiv_announcement_cutoff_utc(now_utc=now_utc)
        self.assertEqual(cutoff, datetime(2026, 3, 13, 0, 0, tzinfo=timezone.utc))


if __name__ == "__main__":
    unittest.main()
