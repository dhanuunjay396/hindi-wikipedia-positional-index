"""Search, evaluation, index checks, and the command-line interface."""
import argparse
import json
import math
import re
import sys
import time
import unicodedata
from pathlib import Path

from prepare_data import positioned_tokens
from settings import (
    CATALOG_PATH, DEFAULT_RESULTS, DOCSTORE_PATH, LEXICON_PATH, METADATA_PATH,
    BM25_B, BM25_K1, POSTINGS_PATH, ROOT,
)

SAMPLE_QUERIES = [
    "भारत", "भारत AND इतिहास", "भारत OR नेपाल", "भारत NOT नेपाल", '"भारत की राजधानी"',
    "दिल्ली", "हिंदी भाषा", "महात्मा गांधी", "गंगा नदी", "भारतीय इतिहास", "नेपाल", "विज्ञान",
    "सौर मंडल", "साहित्य", "राजस्थान", "भारतीय संविधान", "मुंबई", "हिमालय", "शिक्षा", "कंप्यूटर",
]


def load_index():
    required = (LEXICON_PATH, POSTINGS_PATH, DOCSTORE_PATH, CATALOG_PATH, METADATA_PATH)
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("Index files missing: " + ", ".join(missing) + ". Run prepare_data.py.")
    try:
        lexicon = json.loads(LEXICON_PATH.read_text(encoding="utf-8"))
        catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
        if metadata.get("format_version") != 1:
            raise ValueError("Unsupported index format. Run prepare_data.py to rebuild the index.")
        for term, item in lexicon.items():
            if not all(isinstance(item.get(key), int) and item[key] >= 0 for key in ("cf", "df", "offset", "length")):
                raise ValueError(f"Invalid vocabulary entry for {term!r}.")
        if metadata.get("document_count") != len(catalog) or metadata.get("vocabulary_size") != len(lexicon):
            raise ValueError("Index metadata does not match the catalog or vocabulary. Rebuild the index.")
        return {"lexicon": lexicon, "catalog": catalog, "metadata": metadata,
                "postings_path": POSTINGS_PATH, "docstore_path": DOCSTORE_PATH}
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"Index metadata is unreadable: {exc}") from exc


def get_postings(index, term):
    """Read a term's positional record from disk without loading all postings."""
    item = index["lexicon"].get(term)
    if item is None:
        return {}
    try:
        with index["postings_path"].open("rb") as stream:
            stream.seek(item["offset"])
            records = json.loads(stream.read(item["length"]).decode("utf-8"))
        if not isinstance(records, dict) or len(records) != item["df"]:
            raise ValueError("Document frequency does not match the saved record.")
        if sum(len(positions) for positions in records.values()) != item["cf"]:
            raise ValueError("Collection frequency does not match the saved record.")
        for doc_id, positions in records.items():
            if doc_id not in index["catalog"] or not isinstance(positions, list):
                raise ValueError(f"Invalid posting for {term!r} in document {doc_id!r}.")
            if positions != sorted(set(positions)) or any(not isinstance(pos, int) or pos < 1 for pos in positions):
                raise ValueError(f"Positions must be unique, positive, and sorted for {term!r}.")
        return records
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise ValueError(f"Cannot read postings for {term!r}: {exc}") from exc


def bm25(index, terms, candidates=None):
    """Return BM25 scores using the positive IDF form."""
    count = index["metadata"]["document_count"]
    average_length = index["metadata"]["average_document_length"]
    scores = {}
    for term in set(terms):
        item = index["lexicon"].get(term)
        if not item or not item["df"]:
            continue
        postings = get_postings(index, term)
        idf = math.log(1 + (count - item["df"] + 0.5) / (item["df"] + 0.5))
        for doc_id, positions in postings.items():
            if candidates is not None and doc_id not in candidates:
                continue
            length = index["catalog"][doc_id]["length"]
            tf = len(positions)
            norm = BM25_K1 * (1 - BM25_B + BM25_B * length / average_length) if average_length else BM25_K1
            scores[doc_id] = scores.get(doc_id, 0) + idf * tf * (BM25_K1 + 1) / (tf + norm)
    return scores


def phrase_docs(index, terms):
    if not terms:
        return set()
    posting_maps = [get_postings(index, term) for term in terms]
    matches = set()
    for doc_id, starts in posting_maps[0].items():
        later_positions = [set(posting_map.get(doc_id, ())) for posting_map in posting_maps[1:]]
        if any(all(start + offset + 1 in later_positions[offset] for offset in range(len(later_positions))) for start in starts):
            matches.add(doc_id)
    return matches


def _boolean_candidates(index, query):
    parts = re.split(r"\s+(AND|OR|NOT)\s+", query, flags=re.I)
    if len(parts) == 1 and re.search(r"\b(?:AND|OR|NOT)\b", query, flags=re.I):
        raise ValueError("Boolean operators need a search term on each side.")
    if len(parts) % 2 != 1:
        raise ValueError("Invalid Boolean query. Use TERM AND|OR|NOT TERM.")

    clauses = [[term for term, _ in positioned_tokens(parts[i])] for i in range(0, len(parts), 2)]
    operators = {"AND", "OR", "NOT"}
    if any(not clause or any(term.upper() in operators for term in clause) for clause in clauses):
        raise ValueError("Boolean operators need a search term on each side.")

    clause_sets = [set.intersection(*(set(get_postings(index, term)) for term in clause)) for clause in clauses]
    current = clause_sets[0]
    for operator, operand in zip(parts[1::2], clause_sets[1:]):
        if operator.upper() == "AND":
            current &= operand
        elif operator.upper() == "OR":
            current |= operand
        else:
            current -= operand
    return current


def _document_text(index, doc_id):
    item = index["catalog"][doc_id]
    with index["docstore_path"].open("rb") as stream:
        stream.seek(item["offset"])
        row = json.loads(stream.read(item["bytes"]).decode("utf-8"))
    if row.get("id") != doc_id:
        raise ValueError(f"Document store offset mismatch for {doc_id}.")
    return row.get("text", "")


def search(index, query, limit=DEFAULT_RESULTS):
    query = (query or "").strip()
    if not query:
        return []
    exact_phrase = len(query) >= 2 and query[0] == query[-1] == '"'
    if '"' in query and not exact_phrase:
        raise ValueError("Wrap the complete exact phrase in double quotes.")

    if exact_phrase:
        query_terms = [term for term, _ in positioned_tokens(query[1:-1], include_stop_words=True)]
        candidates = phrase_docs(index, query_terms)
    else:
        has_boolean = bool(re.search(r"\s+(?:AND|OR|NOT)\s+", query, re.I))
        if has_boolean:
            candidates = _boolean_candidates(index, query)
        else:
            query_terms = [term for term, _ in positioned_tokens(query)]
            candidates = None

    ranking_terms = query_terms if exact_phrase else [
        term for term, _ in positioned_tokens(query) if term.upper() not in {"AND", "OR", "NOT"}
    ]
    scores = bm25(index, ranking_terms, candidates)
    results = []
    for doc_id in sorted(scores, key=scores.get, reverse=True)[:max(0, limit)]:
        text = _document_text(index, doc_id)
        terms = sorted(set(ranking_terms), key=len, reverse=True)
        occurrences = [text.lower().find(term.lower()) for term in terms]
        occurrences = [position for position in occurrences if position >= 0]
        start = max(0, min(occurrences) - 100) if occurrences else 0
        snippet = ("…" if start else "") + text[start:start + 280]
        if start + 280 < len(text):
            snippet += "…"
        for term in terms:
            snippet = re.sub(re.escape(term), lambda match: f"**{match.group(0)}**", snippet, flags=re.I)
        results.append({
            "id": doc_id,
            "title": index["catalog"][doc_id]["title"],
            "score": scores[doc_id],
            "snippet": snippet,
        })
    return results


def evaluate(index):
    for query in SAMPLE_QUERIES:
        started = time.perf_counter()
        results = search(index, query)
        elapsed = time.perf_counter() - started
        print(f"\nQuery: {query} | time: {elapsed:.4f}s | P@10: N/A (manual relevance judgments required)")
        for result in results:
            print(f"  {result['title']} (ID {result['id']}, BM25 {result['score']:.3f})")


def validate_index(index):
    terms = occurrences = byte_count = 0
    with index["postings_path"].open("rb") as stream:
        for term, item in index["lexicon"].items():
            stream.seek(item["offset"])
            raw = stream.read(item["length"])
            byte_count += len(raw)
            records = json.loads(raw.decode("utf-8"))
            if len(records) != item["df"]:
                raise ValueError(f"Document frequency mismatch for {term!r}.")
            collection_frequency = 0
            for doc_id, positions in records.items():
                if doc_id not in index["catalog"] or not positions or positions != sorted(set(positions)):
                    raise ValueError(f"Invalid posting for {term!r}, document {doc_id!r}.")
                collection_frequency += len(positions)
            if collection_frequency != item["cf"]:
                raise ValueError(f"Collection frequency mismatch for {term!r}.")
            terms += 1
            occurrences += collection_frequency
    if byte_count != index["metadata"]["postings_file_bytes"] or terms != index["metadata"]["vocabulary_size"]:
        raise ValueError("Index file size or vocabulary count does not match metadata.")
    print(f"PASS: {terms:,} terms, {occurrences:,} postings, {byte_count:,} bytes; all posting records are valid.")


def generate_report(path):
    index = load_index()
    rare = sorted(
        (term for term in index["lexicon"] if term and all("DEVANAGARI" in unicodedata.name(char, "") for char in term)),
        key=lambda term: (index["lexicon"][term]["df"], index["lexicon"][term]["cf"], term),
    )[:10]
    rows = [
        "Hindi Wikipedia positional index report",
        f"Corpus: {index['metadata']['document_count']:,} documents; vocabulary: {len(index['lexicon']):,} terms.",
        "\nRare Hindi terms (CF, DF, and saved positions):",
    ]
    for term in rare:
        item = index["lexicon"][term]
        rows.append(f"\n{term} — CF {item['cf']}, DF {item['df']}")
        rows.extend(f"  {doc_id}: {positions}" for doc_id, positions in get_postings(index, term).items())

    bharat = set(get_postings(index, "भारत"))
    nepal = set(get_postings(index, "नेपाल"))
    cases = [
        ("Single term", "भारत", len(bharat) > 0, f"{len(bharat)} matching documents"),
        ("Boolean AND", "भारत AND नेपाल", bharat & nepal, f"{len(bharat & nepal)} matching documents"),
        ("Boolean OR", "भारत OR नेपाल", bharat | nepal, f"{len(bharat | nepal)} matching documents"),
        ("Boolean NOT", "भारत NOT नेपाल", bharat - nepal, f"{len(bharat - nepal)} matching documents"),
        ("Exact phrase", '"भारत की राजधानी"', phrase_docs(index, ["भारत", "की", "राजधानी"]), "adjacent positions checked"),
    ]
    rows.append("\n\nSearch examples:")
    for number, (name, query, result, description) in enumerate(cases, 1):
        passed = bool(result)
        rows.extend([f"\n{number}. {name}", f"Query: {query}", f"Result: {description}", f"Status: {'PASS' if passed else 'NO MATCH'}"])
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"Report written to {path}; {len(rare)} rare terms and {len(cases)} query examples.")


def main():
    parser = argparse.ArgumentParser(description="Search and inspect the Hindi Wikipedia index.")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--evaluate", action="store_true", help="run the sample Hindi query set")
    actions.add_argument("--validate", action="store_true", help="check every saved posting")
    actions.add_argument("--report", nargs="?", const=str(ROOT / "output.txt"), help="write a corpus report (default: output.txt)")
    args = parser.parse_args()

    if args.report:
        generate_report(Path(args.report))
        return
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        index = load_index()
    except (FileNotFoundError, ValueError, OSError) as exc:
        print(exc)
        return
    if args.validate:
        validate_index(index)
    elif args.evaluate:
        evaluate(index)
    else:
        _interactive(index)


def _interactive(index):
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    while True:
        try:
            query = input("Hindi search (blank to quit): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not query:
            break
        started = time.perf_counter()
        try:
            results = search(index, query)
        except ValueError as exc:
            print(f"Invalid query: {exc}")
            continue
        print(f"{len(results)} result(s), {time.perf_counter()-started:.4f}s")
        for result in results:
            print(f"\n{result['title']} (ID {result['id']}, BM25 {result['score']:.4f})\n{result['snippet']}")


if __name__ == "__main__":
    main()
