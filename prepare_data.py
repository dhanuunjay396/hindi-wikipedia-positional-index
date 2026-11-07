"""Extract Hindi Wikipedia pages and build the compact disk-backed index."""
import argparse
import bz2
import json
import re
import time
import unicodedata
import xml.etree.ElementTree as ET
from collections import defaultdict

from settings import (
    ARTICLES_PATH, CATALOG_PATH, DATASET_PATH, DOCSTORE_PATH, LEXICON_PATH,
    MAX_ARTICLES, METADATA_PATH, MIN_ARTICLE_LENGTH, POSTINGS_PATH,
)

STOP_WORDS = set("और या का की के को में से पर है हैं था थी थे यह वह एक इस उस इन उन भी ही तो तक लिए द्वारा तथा लेकिन नहीं अपना अपनी अपने जो कि जैसा जैसी जैसे बहुत सभी कुछ कोई क्या कैसे कब कहाँ क्यों जब तब".split())
TOKEN_RE = re.compile(r"[\u0900-\u097F]+|[a-zA-Z0-9]+")


def normalize(text):
    return " ".join(unicodedata.normalize("NFC", text or "").split())


def tokenize(text):
    tokens = []
    for candidate in TOKEN_RE.findall(normalize(text).lower()):
        current = []
        for char in candidate:
            category = unicodedata.category(char)
            if category[0] in {"L", "M", "N"}:
                current.append(char)
            elif current:
                tokens.append("".join(current))
                current = []
        if current:
            tokens.append("".join(current))
    return tokens


def positioned_tokens(text, include_stop_words=False):
    return [(term, position) for position, term in enumerate(tokenize(text), 1)
            if include_stop_words or term not in STOP_WORDS]


def preprocess(text):
    """Return searchable terms with their original, one-based token positions."""
    return positioned_tokens(text)


def clean_wikitext(text):
    text = re.sub(r"(?is)<ref\b[^>]*>.*?</ref\s*>|<ref\b[^>]*/\s*>", " ", text)
    text = re.sub(r"(?is)<(nowiki|gallery|math)\b[^>]*>.*?</\1\s*>", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = re.sub(r"(?ms)^\s*\{\|.*?^\s*\|\}\s*$", " ", text)
    text = re.sub(r"(?m)^\s*\[\[(?:File|Image|Category|चित्र|श्रेणी):[^\]]*\]\]\s*$", " ", text, flags=re.I)
    text = re.sub(r"(?s)\{\{.*?\}\}", " ", text)
    text = re.sub(r"\[\[([^]|]+\|)?([^]]+)\]\]", lambda m: m.group(2), text)
    text = re.sub(r"\[(?:https?://\S+\s*)?([^\]]*)\]", r"\1", text)
    text = re.sub(r"'{2,5}", "", text)
    text = re.sub(r"(?m)^\s*[*#;:]+\s*", "", text)
    return " ".join(text.split())


def extract_articles(limit=MAX_ARTICLES):
    if not DATASET_PATH.is_file():
        raise FileNotFoundError(
            f"Wikipedia dump not found at {DATASET_PATH}. Download the Hindi pages-articles dump first."
        )

    started = time.perf_counter()
    pages = saved = redirects = skipped = 0
    namespace = "{http://www.mediawiki.org/xml/export-0.11/}"
    articles = []
    seen_ids = set()
    root = None

    print(f"Reading compressed dump: {DATASET_PATH}", flush=True)
    with bz2.open(DATASET_PATH, "rb") as stream:
        for event, elem in ET.iterparse(stream, events=("start", "end")):
            if root is None and event == "start":
                root = elem
            if event != "end" or elem.tag != namespace + "page":
                continue

            pages += 1
            if pages % 5_000 == 0:
                print(f"Scanned {pages:,} pages; accepted {saved:,} articles...", flush=True)
            title = elem.findtext(namespace + "title", "")
            page_id = elem.findtext(namespace + "id", "")
            is_redirect = elem.find(namespace + "redirect") is not None
            is_main_namespace = elem.findtext(namespace + "ns", "") == "0"
            revision = elem.find(namespace + "revision")
            raw_text = revision.findtext(namespace + "text", "") if revision is not None else ""

            if is_redirect:
                redirects += 1
            elif is_main_namespace:
                text = clean_wikitext(raw_text)
                disambiguation = "{{disambiguation}}" in raw_text.lower() or "{{dab}}" in raw_text.lower() or "बहुविकल्पी" in title.lower()
                if not disambiguation and len(text) >= MIN_ARTICLE_LENGTH and page_id not in seen_ids:
                    articles.append({"id": int(page_id), "title": title, "text": text})
                    seen_ids.add(page_id)
                    saved += 1
                else:
                    skipped += 1

            elem.clear()
            if root is not None:
                root.clear()
            if saved >= limit:
                break

    ARTICLES_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTICLES_PATH.write_text(json.dumps(articles, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Extracted {saved:,} articles from {pages:,} pages in {time.perf_counter()-started:.1f}s; redirects skipped: {redirects:,}; other pages skipped: {skipped:,}.", flush=True)


def build_index():
    if not ARTICLES_PATH.is_file():
        raise FileNotFoundError(f"Articles file not found at {ARTICLES_PATH}; run extraction first.")

    started = time.perf_counter()
    print(f"Loading articles from {ARTICLES_PATH}...", flush=True)
    articles = json.loads(ARTICLES_PATH.read_text(encoding="utf-8"))
    print(f"Building positional data for {len(articles):,} articles...", flush=True)
    postings = defaultdict(dict)
    catalog = {}
    seen = set()
    total_tokens = 0

    DATASET_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DOCSTORE_PATH.open("wb") as doc_file:
        for number, article in enumerate(articles, 1):
            doc_id = str(article["id"])
            if doc_id in seen:
                continue
            seen.add(doc_id)
            text = article.get("text", "")
            searchable = preprocess(text)
            length = len(searchable)
            total_tokens += length

            positions_by_term = defaultdict(list)
            for term, position in positioned_tokens(text, include_stop_words=True):
                positions_by_term[term].append(position)
            for term, positions in positions_by_term.items():
                postings[term][doc_id] = positions

            encoded = json.dumps({"id": doc_id, "text": text}, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"
            offset = doc_file.tell()
            doc_file.write(encoded)
            catalog[doc_id] = {"title": article.get("title", ""), "length": length, "offset": offset, "bytes": len(encoded)}
            if number % 500 == 0 or number == len(articles):
                print(f"Processed {number:,}/{len(articles):,} articles; {len(postings):,} terms collected.", flush=True)

    lexicon = {}
    print(f"Writing postings for {len(postings):,} terms...", flush=True)
    with POSTINGS_PATH.open("wb") as posting_file:
        for number, term in enumerate(sorted(postings), 1):
            record = postings[term]
            encoded = json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            offset = posting_file.tell()
            posting_file.write(encoded)
            lexicon[term] = {"cf": sum(map(len, record.values())), "df": len(record), "offset": offset, "length": len(encoded)}
            if number % 25_000 == 0 or number == len(postings):
                print(f"Wrote postings for {number:,}/{len(postings):,} terms...", flush=True)

    LEXICON_PATH.write_text(json.dumps(lexicon, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    CATALOG_PATH.write_text(json.dumps(catalog, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    avgdl = total_tokens / len(catalog) if catalog else 0
    metadata = {
        "format_version": 1,
        "document_count": len(catalog),
        "total_indexed_tokens": total_tokens,
        "average_document_length": avgdl,
        "vocabulary_size": len(lexicon),
        "postings_file_bytes": POSTINGS_PATH.stat().st_size,
    }
    METADATA_PATH.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Indexed {len(catalog):,} documents, {len(lexicon):,} terms, and {total_tokens:,} searchable tokens; build time: {time.perf_counter()-started:.1f}s.", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Prepare the Hindi Wikipedia search index.")
    parser.add_argument("--extract", action="store_true", help="refresh articles.json from the compressed dump")
    parser.add_argument("--limit", type=int, default=MAX_ARTICLES, help="maximum articles to extract when using --extract")
    args = parser.parse_args()

    if args.extract or not ARTICLES_PATH.is_file():
        extract_articles(max(1, args.limit))
    else:
        print(f"Using existing articles: {ARTICLES_PATH}")
    build_index()


if __name__ == "__main__":
    main()
