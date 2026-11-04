"""Build an in-memory vocabulary / disk-resident positional postings index."""
import json
import time
from collections import defaultdict

from config import ARTICLES_PATH, DOCSTORE_PATH, LEXICON_PATH, METADATA_PATH, POSTINGS_PATH
from preprocess import positioned_tokens, preprocess


def build():
    if not ARTICLES_PATH.exists():
        raise FileNotFoundError(f"Articles not found: {ARTICLES_PATH}. Run extract_articles.py first.")
    start = time.time()
    articles = json.loads(ARTICLES_PATH.read_text(encoding="utf-8"))
    postings = defaultdict(lambda: defaultdict(list))
    lengths, catalog, seen = {}, {}, set()
    total_tokens = 0
    with DOCSTORE_PATH.open("wb") as docs_file:
        for article in articles:
            docid = str(article["id"])
            if docid in seen:
                continue
            seen.add(docid)
            text = article.get("text", "")
            title = article.get("title", "")
            searchable = preprocess(text)
            lengths[docid] = len(searchable)
            total_tokens += len(searchable)
            for term, pos in positioned_tokens(text, include_stop_words=True):
                postings[term][docid].append(pos)
            encoded = json.dumps({"id": docid, "text": text}, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"
            offset = docs_file.tell()
            docs_file.write(encoded)
            catalog[docid] = {"title": title, "length": lengths[docid], "offset": offset, "bytes": len(encoded)}

    lexicon = {}
    with POSTINGS_PATH.open("wb") as post_file:
        for term in sorted(postings):
            record = {docid: positions for docid, positions in postings[term].items()}
            encoded = json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            offset = post_file.tell()
            post_file.write(encoded)
            lexicon[term] = {"cf": sum(map(len, record.values())), "df": len(record), "offset": offset, "length": len(encoded)}
    LEXICON_PATH.write_text(json.dumps(lexicon, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    avgdl = total_tokens / len(catalog) if catalog else 0
    metadata = {"format_version": 1, "document_count": len(catalog), "total_indexed_tokens": total_tokens,
                "average_document_length": avgdl, "vocabulary_size": len(lexicon),
                "postings_file_bytes": POSTINGS_PATH.stat().st_size}
    METADATA_PATH.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    (DOCSTORE_PATH.with_suffix(".catalog.json")).write_text(json.dumps(catalog, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Documents: {len(catalog)}; terms: {len(lexicon)}; searchable tokens: {total_tokens}; postings: {POSTINGS_PATH.stat().st_size:,} bytes; build time: {time.time()-start:.1f}s")


if __name__ == "__main__":
    build()
