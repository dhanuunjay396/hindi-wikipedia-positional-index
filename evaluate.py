import time
import sys

from search import load_index, search

# Edit relevant_ids after making manual judgments; empty lists are intentionally unlabeled.
QUERIES = [
    {"query": q, "relevant_ids": []} for q in [
        "भारत", "भारत AND इतिहास", "भारत OR नेपाल", "भारत NOT नेपाल", '"भारत की राजधानी"',
        "दिल्ली", "हिंदी भाषा", "महात्मा गांधी", "गंगा नदी", "भारतीय इतिहास", "नेपाल", "विज्ञान",
        "सौर मंडल", "साहित्य", "राजस्थान", "भारतीय संविधान", "मुंबई", "हिमालय", "शिक्षा", "कंप्यूटर"
    ]
]


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    index = load_index()
    for item in QUERIES:
        start = time.perf_counter()
        results = search(index, item["query"], 10)
        elapsed = time.perf_counter() - start
        relevant = set(map(str, item["relevant_ids"]))
        if relevant:
            p10_text = f"{sum(r['id'] in relevant for r in results) / 10:.3f}"
        else:
            p10_text = "N/A (manual relevance judgments required)"
        print(f"\nQuery: {item['query']} | time: {elapsed:.4f}s | relevant IDs: {sorted(relevant) or 'not judged'} | P@10: {p10_text}")
        for r in results: print(f"  {r['title']} (ID {r['id']}, {r['score']:.3f})")


if __name__ == "__main__": main()
