import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import build_index
import search


class DiskIndexTests(unittest.TestCase):
    def setUp(self):
        temp_root = Path(__file__).resolve().parent / ".tmp"
        temp_root.mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=temp_root)
        root = Path(self.tmp.name)
        self.paths = {
            "ARTICLES_PATH": root / "articles.json", "LEXICON_PATH": root / "lexicon.json",
            "POSTINGS_PATH": root / "postings.jsonl", "DOCSTORE_PATH": root / "documents.jsonl",
            "METADATA_PATH": root / "metadata.json",
        }
        articles = [
            {"id": 101, "title": "पहला", "text": "भारत भारत की राजधानी दिल्ली"},
            {"id": 202, "title": "दूसरा", "text": "भारत और भाषा हिंदी"},
            {"id": 303, "title": "तीसरा", "text": "दिल्ली भारत भाषा"},
        ]
        self.paths["ARTICLES_PATH"].write_text(json.dumps(articles, ensure_ascii=False), encoding="utf-8")
        self.patches = [patch.object(build_index, name, path) for name, path in self.paths.items()]
        for item in self.patches: item.start()
        self.search_patches = [patch.object(search, name, path) for name, path in self.paths.items() if name != "ARTICLES_PATH"]
        for item in self.search_patches: item.start()
        build_index.build()
        self.index = search.load_index()

    def tearDown(self):
        for item in self.patches + self.search_patches: item.stop()
        self.tmp.cleanup()

    def test_vocab_in_memory_and_postings_on_disk(self):
        self.assertIn("lexicon", self.index)
        self.assertNotIn("postings", self.index)
        self.assertNotIn("भारत", self.index)  # no full postings map attached to engine
        self.assertTrue(self.index["postings_path"].is_file())
        self.assertEqual(search.get_postings(self.index, "भारत"), {"101": [1, 2], "202": [1], "303": [2]})

    def test_cf_df_and_positions(self):
        meta = self.index["lexicon"]["भारत"]
        self.assertEqual((meta["cf"], meta["df"]), (4, 3))
        self.assertGreaterEqual(meta["cf"], meta["df"])
        self.assertEqual(self.index["lexicon"]["दिल्ली"]["cf"], 2)

    def test_phrase_uses_positions_and_stopwords(self):
        self.assertEqual({r["id"] for r in search.search(self.index, '"भारत की राजधानी"')}, {"101"})
        self.assertEqual(search.phrase_docs(self.index, ["भारत", "राजधानी"]), set())

    def test_boolean_unknown_and_restart(self):
        self.assertEqual({r["id"] for r in search.search(self.index, "भारत AND दिल्ली")}, {"101", "303"})
        self.assertEqual({r["id"] for r in search.search(self.index, "भारत OR हिंदी")}, {"101", "202", "303"})
        self.assertEqual(search.search(self.index, "अनुपस्थित"), [])
        reopened = search.load_index()
        self.assertEqual({r["id"] for r in search.search(reopened, "भारत")}, {"101", "202", "303"})


if __name__ == "__main__":
    unittest.main()
