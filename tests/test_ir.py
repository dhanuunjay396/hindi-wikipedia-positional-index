import json
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import prepare_data
import ir_search


class DiskIndexTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        prefix = root / f".ir-test-{uuid.uuid4().hex}"
        self.paths = {
            "ARTICLES_PATH": Path(f"{prefix}-articles.json"),
            "LEXICON_PATH": Path(f"{prefix}-lexicon.json"),
            "POSTINGS_PATH": Path(f"{prefix}-postings.jsonl"),
            "DOCSTORE_PATH": Path(f"{prefix}-documents.jsonl"),
            "CATALOG_PATH": Path(f"{prefix}-catalog.json"),
            "METADATA_PATH": Path(f"{prefix}-metadata.json"),
        }
        articles = [
            {"id": 101, "title": "पहला", "text": "भारत भारत की राजधानी दिल्ली"},
            {"id": 202, "title": "दूसरा", "text": "भारत और भाषा हिंदी"},
            {"id": 303, "title": "तीसरा", "text": "दिल्ली भारत भाषा"},
        ]
        self.paths["ARTICLES_PATH"].write_text(json.dumps(articles, ensure_ascii=False), encoding="utf-8")
        self.patches = [patch.object(prepare_data, name, path) for name, path in self.paths.items()]
        for item in self.patches: item.start()
        self.search_patches = [patch.object(ir_search, name, path) for name, path in self.paths.items() if name != "ARTICLES_PATH"]
        for item in self.search_patches: item.start()
        prepare_data.build_index()
        self.index = ir_search.load_index()

    def tearDown(self):
        for item in self.patches + self.search_patches: item.stop()
        for path in self.paths.values():
            path.unlink(missing_ok=True)

    def test_vocab_in_memory_and_postings_on_disk(self):
        self.assertIn("lexicon", self.index)
        self.assertNotIn("postings", self.index)
        self.assertNotIn("भारत", self.index)  # no full postings map attached to engine
        self.assertTrue(self.index["postings_path"].is_file())
        self.assertEqual(ir_search.get_postings(self.index, "भारत"), {"101": [1, 2], "202": [1], "303": [2]})

    def test_cf_df_and_positions(self):
        meta = self.index["lexicon"]["भारत"]
        self.assertEqual((meta["cf"], meta["df"]), (4, 3))
        self.assertGreaterEqual(meta["cf"], meta["df"])
        self.assertEqual(self.index["lexicon"]["दिल्ली"]["cf"], 2)

    def test_hindi_positions_and_punctuation(self):
        self.assertEqual(prepare_data.preprocess("भारत एक महान देश है"), [("भारत", 1), ("महान", 3), ("देश", 4)])
        self.assertEqual(prepare_data.tokenize("भारत।नेपाल !!!"), ["भारत", "नेपाल"])
        self.assertEqual(prepare_data.tokenize(""), [])

    def test_phrase_uses_positions_and_stopwords(self):
        self.assertEqual({r["id"] for r in ir_search.search(self.index, '"भारत की राजधानी"')}, {"101"})
        self.assertEqual(ir_search.phrase_docs(self.index, ["भारत", "राजधानी"]), set())

    def test_boolean_unknown_and_restart(self):
        self.assertEqual({r["id"] for r in ir_search.search(self.index, "भारत AND दिल्ली")}, {"101", "303"})
        self.assertEqual({r["id"] for r in ir_search.search(self.index, "भारत OR हिंदी")}, {"101", "202", "303"})
        self.assertEqual({r["id"] for r in ir_search.search(self.index, "भारत NOT दिल्ली")}, {"202"})
        self.assertEqual(ir_search.search(self.index, "अनुपस्थित"), [])
        reopened = ir_search.load_index()
        self.assertEqual({r["id"] for r in ir_search.search(reopened, "भारत")}, {"101", "202", "303"})


if __name__ == "__main__":
    unittest.main()
