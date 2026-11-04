"""Create the required real-corpus rare-term and query report."""
import json
import unicodedata
from pathlib import Path

from config import ARTICLES_PATH
from preprocess import positioned_tokens
from search import get_postings, load_index, phrase_docs, search


def _is_hindi(term):
    return (bool(term) and unicodedata.category(term[0]).startswith("L") and
            sum(unicodedata.category(char).startswith("L") for char in term) >= 2 and
            all("DEVANAGARI" in unicodedata.name(char, "") for char in term))


def generate(path=Path("output.txt")):
    index = load_index()
    rare = sorted((t for t in index["lexicon"] if _is_hindi(t) and len(t) > 1),
                  key=lambda t: (index["lexicon"][t]["df"], index["lexicon"][t]["cf"], t))[:10]
    rows = ["PART A — 10 rare Hindi terms from the indexed Wikipedia corpus",
            f"Corpus: {index['metadata']['document_count']} documents; vocabulary: {len(index['lexicon'])} terms."]
    for term in rare:
        stats = index["lexicon"][term]
        rows += [f"\nRare Term: {term}", f"CF: {stats['cf']}", f"DF: {stats['df']}", "Postings:"]
        rows += [f"- Document {docid} → {positions}" for docid, positions in get_postings(index, term).items()]

    repeated_term = next((t for t in sorted(index["lexicon"], key=lambda x: (index["lexicon"][x]["df"], x)) if _is_hindi(t)
                          if any(len(p) > 1 for p in get_postings(index, t).values())), None)
    # Find a real adjacent-token pair that is present as an exact phrase.
    phrase_terms = None
    with ARTICLES_PATH.open(encoding="utf-8") as src:
        for article in json.load(src):
            tokens = [term for term, _ in positioned_tokens(article.get("text", ""), include_stop_words=True)]
            for a, b in zip(tokens, tokens[1:]):
                if phrase_docs(index, [a, b]):
                    phrase_terms = [a, b]
                    break
            if phrase_terms: break
    if not phrase_terms:
        raise RuntimeError("Could not find an indexed two-token phrase")
    rare_term = rare[0]
    cases = []
    single = "भारत"
    single_posts = get_postings(index, single)
    cases.append(("Single-term positional retrieval", single,
                  f"Return CF={index['lexicon'][single]['cf']}, DF={index['lexicon'][single]['df']} and positional postings.",
                  f"CF={index['lexicon'][single]['cf']}, DF={index['lexicon'][single]['df']}; first postings: {list(single_posts.items())[:3]}",
                  bool(single_posts)))
    repeated_posts = get_postings(index, repeated_term)
    repeated_doc, positions = next((d, p) for d, p in repeated_posts.items() if len(p) > 1)
    cases.append(("Repeated-term positional retrieval", repeated_term,
                  "At least one document must expose multiple ascending positions for the same term.",
                  f"Document {repeated_doc} → {positions}", len(positions) > 1 and positions == sorted(positions)))
    phrase_query = '"' + " ".join(phrase_terms) + '"'
    phrase_results = search(index, phrase_query, index["metadata"]["document_count"])
    cases.append(("Two-word exact phrase", phrase_query,
                  "Return only documents containing the two terms at adjacent original-token positions.",
                  f"{len(phrase_results)} result(s); first IDs: {[r['id'] for r in phrase_results[:10]]}", bool(phrase_results)))
    bool_query = "भारत AND नेपाल"
    and_ids = {r["id"] for r in search(index, bool_query, index["metadata"]["document_count"])}
    or_ids = {r["id"] for r in search(index, "भारत OR नेपाल", index["metadata"]["document_count"])}
    expected_and = set(get_postings(index, "भारत")) & set(get_postings(index, "नेपाल"))
    expected_or = set(get_postings(index, "भारत")) | set(get_postings(index, "नेपाल"))
    cases.append(("Boolean AND / OR", "भारत AND नेपाल; भारत OR नेपाल",
                  "AND returns the intersection; OR returns the union.",
                  f"AND {len(and_ids)} IDs: {sorted(and_ids)[:10]}; OR {len(or_ids)} IDs: {sorted(or_ids)[:10]}",
                  and_ids == expected_and and or_ids == expected_or))
    rare_posts = get_postings(index, rare_term)
    cases.append(("Rare-term retrieval with positions", rare_term,
                  f"Return CF={index['lexicon'][rare_term]['cf']}, DF={index['lexicon'][rare_term]['df']} and the exact postings.",
                  f"CF={index['lexicon'][rare_term]['cf']}, DF={index['lexicon'][rare_term]['df']}; {list(rare_posts.items())}",
                  bool(rare_posts) and len(rare_posts) == index["lexicon"][rare_term]["df"]))
    rows += ["\n\nPART B — Five reproducible search test cases"]
    for i, (name, query, expected, actual, passed) in enumerate(cases, 1):
        rows += [f"\nTest {i}: {name}", f"Query: {query}", f"Expected behavior: {expected}",
                 f"Actual output: {actual}", f"Status: {'PASS' if passed else 'FAIL'}"]
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"Wrote {path.resolve()}; rare terms: {len(rare)}; cases: {sum(c[-1] for c in cases)}/{len(cases)} passed")


if __name__ == "__main__":
    generate()
