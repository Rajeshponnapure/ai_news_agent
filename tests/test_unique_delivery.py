import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database.db import Database
from processing.pipeline import ProcessingPipeline


class UniqueDeliveryRegressionTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_ai_updates.db"
        self.db = Database(db_path=str(self.db_path))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_duplicate_ingest_is_suppressed_and_sent_rows_are_skipped(self):
        pipeline = ProcessingPipeline()
        raw_entries = [
            {
                "title": "Introducing GPT-5.5",
                "company": "OpenAI",
                "summary": "OpenAI announced a current model release on its news index.",
                "timestamp": "2026-05-18T00:00:00+00:00",
                "source_url": "https://openai.com/index/introducing-gpt-5-5/",
                "source_name": "rss",
                "is_launch": True,
                "is_top_company": True,
            },
            {
                "title": "Introducing GPT-5.5",
                "company": "OpenAI",
                "summary": "OpenAI announced a current model release on its news index.",
                "timestamp": "2026-05-18T00:00:00+00:00",
                "source_url": "https://openai.com/index/introducing-gpt-5-5/",
                "source_name": "rss",
                "is_launch": True,
                "is_top_company": True,
            },
        ]

        with patch("processing.pipeline.get_db", return_value=self.db):
            stored = pipeline.ingest_and_store(raw_entries)

        self.assertEqual(stored, 1)

        unsent = self.db.get_top_updates()
        self.assertEqual(len(unsent), 1)
        self.assertEqual(unsent[0]["title"], "Introducing GPT-5.5")

        self.db.mark_digest_sent([unsent[0]["id"]])
        self.assertEqual(self.db.get_top_updates(), [])

        with patch("processing.pipeline.get_db", return_value=self.db):
            stored_again = pipeline.ingest_and_store([
                {
                    "title": "Introducing GPT-5.5",
                    "company": "OpenAI",
                    "summary": "OpenAI announced a current model release on its news index.",
                    "timestamp": "2026-05-18T00:00:00+00:00",
                    "source_url": "https://openai.com/index/introducing-gpt-5-5/",
                    "source_name": "rss",
                    "is_launch": True,
                    "is_top_company": True,
                }
            ])

        self.assertEqual(stored_again, 0)


if __name__ == "__main__":
    unittest.main()