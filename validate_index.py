"""Check every on-disk posting record against its in-memory vocabulary metadata."""
import json

from search import load_index


def validate():
    index = load_index()
    terms = occurrences = posting_bytes = 0
    with index["postings_path"].open("rb") as stream:
        for term, meta in index["lexicon"].items():
            stream.seek(meta["offset"])
            raw = stream.read(meta["length"])
            posting_bytes += len(raw)
            records = json.loads(raw.decode("utf-8"))
            if not isinstance(records, dict) or len(records) != meta["df"]:
                raise ValueError(f"DF mismatch for {term!r}")
            cf = 0
            for docid, positions in records.items():
                if docid not in index["catalog"]:
                    raise ValueError(f"Unknown document {docid!r} for term {term!r}")
                if not isinstance(positions, list) or not positions or positions != sorted(set(positions)) or any(not isinstance(p, int) or p < 1 for p in positions):
                    raise ValueError(f"Invalid positions for {term!r} in document {docid!r}")
                cf += len(positions)
            if cf != meta["cf"] or cf < meta["df"]:
                raise ValueError(f"CF mismatch for {term!r}")
            terms += 1
            occurrences += cf
    if posting_bytes != index["metadata"]["postings_file_bytes"]:
        raise ValueError("Postings file length does not match index metadata")
    if terms != index["metadata"]["vocabulary_size"]:
        raise ValueError("Vocabulary size does not match index metadata")
    print(f"PASS: {terms:,} terms; {occurrences:,} occurrences; {posting_bytes:,} postings bytes; all CF/DF, IDs, and positions verified")


if __name__ == "__main__":
    validate()
