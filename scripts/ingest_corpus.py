#!/usr/bin/env python3
"""Ingest the project's own documents into the retrieval index.

  scripts/ingest_corpus.py                       # thesis + profile
  scripts/ingest_corpus.py --dry-run             # chunk and report, embed nothing
  scripts/ingest_corpus.py --file some.pdf

Run from the backend directory with its virtualenv, so the .env is picked up:

  cd backend && .venv/bin/python ../scripts/ingest_corpus.py

Text is extracted per page so a retrieved passage can cite a page number.
Ingestion is idempotent: chunk ids are the SHA-256 of the chunk's own text, so
re-running after editing one chapter re-embeds only what changed and upserts
over the same ids.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

DEFAULT_DOCS = [
    (REPO / "thesis" / "old_thesis.pdf", "thesis"),
    (REPO / "Profile.pdf", "profile"),
]


def load_env() -> None:
    """Read backend/.env by hand; values contain spaces, so `source` is unsafe."""
    envp = REPO / "backend" / ".env"
    if not envp.exists():
        return
    import os

    for line in envp.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def pages_of(path: Path) -> list[tuple[int, str]]:
    import fitz  # PyMuPDF

    doc = fitz.open(path)
    out = []
    for i, page in enumerate(doc, start=1):
        text = page.get_text("text").strip()
        if text:
            out.append((i, text))
    doc.close()
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", action="append", default=[])
    ap.add_argument("--namespace", default=None,
                    help="override; by default each document goes in its own namespace")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    load_env()
    from app.services.rag_service import Chunk, chunk_text, count_tokens, get_rag_service

    docs = ([(Path(f), Path(f).stem) for f in args.file] if args.file else DEFAULT_DOCS)

    # Each document gets its own namespace. A single top-k over the union is
    # dominated by whichever document has the most chunks, which measurably hid
    # the 4-chunk profile behind the 56-chunk thesis.
    per_ns: dict[str, list[Chunk]] = {}
    all_chunks: list[Chunk] = []
    print(f"{'document':28} {'pages':>6} {'tokens':>9} {'chunks':>7}")
    for path, label in docs:
        if not path.exists():
            print(f"  {path} not found, skipping")
            continue
        pages = pages_of(path)
        chunks: list[Chunk] = []
        tokens = 0
        for pageno, text in pages:
            tokens += count_tokens(text)
            chunks.extend(chunk_text(text, source=label, page=pageno))
        per_ns.setdefault(args.namespace or label, []).extend(chunks)
        all_chunks.extend(chunks)
        print(f"{label:28} {len(pages):6} {tokens:9} {len(chunks):7}")

    if not all_chunks:
        print("nothing to ingest")
        return 1

    sizes = sorted(count_tokens(c.text) for c in all_chunks)
    uniq = len({c.uid for c in all_chunks})
    print(f"\n  total chunks       {len(all_chunks)}  ({uniq} unique by content)")
    print(f"  chunk tokens       min {sizes[0]}  median {sizes[len(sizes)//2]}  max {sizes[-1]}")

    if args.dry_run:
        print("\n  --dry-run: nothing embedded or upserted")
        return 0

    rag = get_rag_service()
    print(f"\n  embedding with {rag.status()['embedding_model']} -> index '{rag.index_name}'")
    total = 0
    for ns, chunks in per_ns.items():
        res = rag.ingest(chunks, namespace=ns)
        total += res["upserted"]
        print(f"  namespace '{ns}': upserted {res['upserted']} vectors")
    print(f"  {total} vectors total "
          f"({rag.stats.embed_cache_hits} embeddings served from cache, "
          f"{rag.stats.embed_calls} API calls)")
    st = rag.status()
    print(f"  index now holds {st['vectors']} vectors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
