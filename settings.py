"""Shared paths and settings for the Hindi Wikipedia search project."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"

DATASET_PATH = DATA_DIR / "hiwiki-latest-pages-articles.xml.bz2"
ARTICLES_PATH = DATA_DIR / "articles.json"
LEXICON_PATH = DATA_DIR / "lexicon.json"
POSTINGS_PATH = DATA_DIR / "postings.jsonl"
DOCSTORE_PATH = DATA_DIR / "documents.jsonl"
CATALOG_PATH = DATA_DIR / "documents.catalog.json"
METADATA_PATH = DATA_DIR / "metadata.json"

LANGUAGE = "hiwiki"
MAX_ARTICLES = 10_000
MIN_ARTICLE_LENGTH = 100
BM25_K1 = 1.5
BM25_B = 0.75
DEFAULT_RESULTS = 10
FLASK_DEBUG = False
