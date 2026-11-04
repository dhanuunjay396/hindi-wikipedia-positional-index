"""Search a disk-backed positional index with only vocabulary metadata in RAM."""
import json
import math
import re
import sys
import time

from config import (DEFAULT_RESULTS, DOCSTORE_PATH, LEXICON_PATH, METADATA_PATH,
                    POSTINGS_PATH, BM25_B, BM25_K1)
from preprocess import positioned_tokens


def load_index():
    required = (LEXICON_PATH, POSTINGS_PATH, DOCSTORE_PATH, DOCSTORE_PATH.with_suffix(".catalog.json"), METADATA_PATH)
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Index files missing: " + ", ".join(missing) + ". Run build_index.py.")
    try:
        lexicon = json.loads(LEXICON_PATH.read_text(encoding="utf-8"))
        catalog = json.loads(DOCSTORE_PATH.with_suffix(".catalog.json").read_text(encoding="utf-8"))
        metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
        for term, item in lexicon.items():
            if not all(isinstance(item.get(k), int) and item[k] >= 0 for k in ("cf", "df", "offset", "length")):
                raise ValueError(f"Invalid vocabulary metadata for {term!r}")
        if metadata.get("format_version") != 1:
            raise ValueError("Unsupported or incomplete index metadata; rebuild the index.")
        return {"lexicon": lexicon, "catalog": catalog, "metadata": metadata,
                "postings_path": POSTINGS_PATH, "docstore_path": DOCSTORE_PATH}
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"Corrupted index metadata: {exc}") from exc


def get_postings(index, term):
    """Read only one requested term's record from the postings file."""
    if term not in index["lexicon"]:
        return {}
    item = index["lexicon"][term]
    try:
        with index["postings_path"].open("rb") as stream:
            stream.seek(item["offset"])
            payload = stream.read(item["length"])
        records = json.loads(payload.decode("utf-8"))
        if not isinstance(records, dict) or len(records) != item["df"] or sum(map(len, records.values())) != item["cf"]:
            raise ValueError("Posting counts do not match vocabulary metadata")
        for docid, positions in records.items():
            if docid not in index["catalog"] or not isinstance(positions, list) or positions != sorted(set(positions)) or any(not isinstance(p, int) or p < 1 for p in positions):
                raise ValueError(f"Invalid posting for term {term!r}, document {docid!r}")
        return records
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise ValueError(f"Cannot read postings for {term!r}: {exc}") from exc


def bm25(index, terms, candidates=None):
    n = index["metadata"]["document_count"]
    avgdl = index["metadata"]["average_document_length"]
    scores = {}
    for term in set(terms):
        docs = get_postings(index, term)
        df = index["lexicon"].get(term, {}).get("df", 0)
        if not df:
            continue
        idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
        for docid, positions in docs.items():
            if candidates is not None and docid not in candidates:
                continue
            dl = index["catalog"][docid]["length"]
            tf = len(positions)
            denom = tf + BM25_K1 * (1 - BM25_B + BM25_B * dl / avgdl) if avgdl else tf + BM25_K1
            scores[docid] = scores.get(docid, 0) + idf * tf * (BM25_K1 + 1) / denom
    return scores


def phrase_docs(index, tokens):
    if not tokens:
        return set()
    maps = [get_postings(index, token) for token in tokens]
    found = set()
    for docid, starts in maps[0].items():
        later = [set(mapping.get(docid, ())) for mapping in maps[1:]]
        if any(all(pos + offset + 1 in later[offset] for offset in range(len(later))) for pos in starts):
            found.add(docid)
    return found


def _doc_text(index, docid):
    entry = index["catalog"][docid]
    with index["docstore_path"].open("rb") as stream:
        stream.seek(entry["offset"])
        row = json.loads(stream.read(entry["bytes"]).decode("utf-8"))
    if row.get("id") != docid:
        raise ValueError(f"Document store offset mismatch for {docid}")
    return row.get("text", "")


def search(index, query, limit=DEFAULT_RESULTS):
    query = (query or "").strip()
    if not query:
        return []
    phrase = len(query) >= 2 and query[0] == query[-1] == '"'
    if '"' in query and not phrase:
        raise ValueError('Use double quotes around the entire exact phrase.')
    if phrase:
        terms = [t for t, _ in positioned_tokens(query[1:-1], include_stop_words=True)]
        candidates = phrase_docs(index, terms)
    else:
        parts = re.split(r"\s+(AND|OR|NOT)\s+", query, flags=re.I)
        if len(parts) == 1 and re.search(r"\b(?:AND|OR|NOT)\b", query, flags=re.I):
            raise ValueError("Boolean operators need a search term on each side.")
        if len(parts) > 1:
            if len(parts) % 2 != 1:
                raise ValueError("Invalid Boolean query. Use TERM AND|OR|NOT TERM.")
            clauses = [[t for t, _ in positioned_tokens(parts[i])] for i in range(0, len(parts), 2)]
            if any(not c or any(t.upper() in {"AND", "OR", "NOT"} for t in c) for c in clauses):
                raise ValueError("Boolean operators need a search term on each side.")
            clause_sets = [set.intersection(*(set(get_postings(index, t)) for t in c)) for c in clauses]
            candidates = clause_sets[0]
            for op, operand in zip(parts[1::2], clause_sets[1:]):
                if op.upper() == "AND": candidates &= operand
                elif op.upper() == "OR": candidates |= operand
                else: candidates -= operand
        else:
            terms = [t for t, _ in positioned_tokens(query)]
            candidates = None
    rank_terms = terms if phrase else [t for t, _ in positioned_tokens(query) if t.upper() not in {"AND", "OR", "NOT"}]
    scores = bm25(index, rank_terms, candidates)
    results = []
    for docid in sorted(scores, key=scores.get, reverse=True)[:limit]:
        text = _doc_text(index, docid)
        terms_re = sorted(set(rank_terms), key=len, reverse=True)
        matches = [text.lower().find(term.lower()) for term in terms_re]
        matches = [p for p in matches if p >= 0]
        start = max(0, min(matches) - 100) if matches else 0
        snippet = ("…" if start else "") + text[start:start + 280]
        if start + 280 < len(text): snippet += "…"
        for term in terms_re:
            snippet = re.sub(re.escape(term), lambda m: f"**{m.group(0)}**", snippet, flags=re.I)
        results.append({"id": docid, "title": index["catalog"][docid]["title"], "score": scores[docid], "snippet": snippet})
    return results


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        index = load_index()
    except (FileNotFoundError, ValueError, OSError) as exc:
        print(exc); return
    while True:
        try: query = input("Hindi search (blank to quit): ").strip()
        except (EOFError, KeyboardInterrupt): break
        if not query: break
        start = time.perf_counter()
        try: results = search(index, query)
        except Exception as exc:
            print(f"Invalid query: {exc}"); continue
        print(f"{len(results)} result(s), {time.perf_counter()-start:.4f}s")
        for row in results:
            print(f"\n{row['title']} (ID {row['id']}, BM25 {row['score']:.4f})\n{row['snippet']}")


if __name__ == "__main__": main()
