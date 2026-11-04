from pathlib import Path

ROOT = Path(__file__).resolve().parent
LANGUAGE = "hiwiki"
LANGUAGE_NAME = "Hindi"
MAX_ARTICLES = 10000
MIN_ARTICLE_LENGTH = 100
DATA_DIR = ROOT / "data"
DATASET_PATH = DATA_DIR / "hiwiki-latest-pages-articles.xml.bz2"
ARTICLES_PATH = DATA_DIR / "articles.json"
INDEX_PATH = DATA_DIR / "positional_index.pkl"  # legacy index path; retained for migration awareness
LEXICON_PATH = DATA_DIR / "lexicon.json"
POSTINGS_PATH = DATA_DIR / "postings.jsonl"
DOCSTORE_PATH = DATA_DIR / "documents.jsonl"
METADATA_PATH = DATA_DIR / "metadata.json"
BM25_K1 = 1.5
BM25_B = 0.75
DEFAULT_RESULTS = 10
FLASK_DEBUG = False
