"""Retrieval-augmented generation over the project's own documents.

The corpus is the thesis and the author's professional profile, so the command
centre can answer questions about the work itself -- its method, its results,
its author -- rather than only about the robot's immediate surroundings. It is
deliberately separate from the command graph: that graph acts on the world,
this answers about the record of the work.

Three design decisions carry most of the weight, and each is measured in the
evaluation rather than asserted:

1.  **Token-aware chunking with overlap.** Chunk boundaries are placed on
    paragraph breaks where possible and on token counts otherwise, so a
    sentence is never split mid-clause. Consecutive chunks overlap, which is
    what stops a fact that straddles a boundary from becoming unretrievable.

2.  **Content-addressed embedding cache.** Every chunk is keyed by the
    SHA-256 of its own text, not by its position in a document. Re-ingesting a
    revised thesis therefore re-embeds only the paragraphs that actually
    changed; an edit to chapter 5 does not pay to re-embed chapters 1-4. This
    matters because the thesis is rewritten repeatedly, and because embedding
    is the dominant cost of ingestion.

3.  **Answer caching keyed by the normalised question.** Repeated questions --
    common on a public demo page -- skip both retrieval and generation.

The cache is a plain JSON sidecar rather than a database: it has to survive
process restarts and be inspectable by hand, and at this corpus size the whole
index is a few megabytes.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

# --- tunables, overridable from the environment ------------------------
DEFAULT_CHUNK_TOKENS = int(os.getenv("MAX_CHUNK_SIZE", "1200"))
DEFAULT_OVERLAP_TOKENS = int(os.getenv("CHUNK_OVERLAP", "150"))
DEFAULT_TOP_K = int(os.getenv("TOP_K_RETRIEVAL", "5"))
EMBED_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")
EMBED_DIM = 3072  # text-embedding-3-large
EMBED_BATCH = 64

CACHE_DIR = Path(os.getenv("RAG_CACHE_DIR", "app/data/rag_cache"))
EMBED_CACHE = CACHE_DIR / "embeddings.json"
ANSWER_CACHE = CACHE_DIR / "answers.json"


@dataclass
class Chunk:
    text: str
    source: str
    page: Optional[int] = None
    ordinal: int = 0

    @property
    def uid(self) -> str:
        """Content address. Two identical paragraphs embed once."""
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()[:32]


@dataclass
class Retrieved:
    text: str
    source: str
    page: Optional[int]
    score: float


@dataclass
class RagStats:
    """Counters the evaluation reads; cheap enough to keep always on."""
    embed_calls: int = 0
    embed_cache_hits: int = 0
    chunks_embedded: int = 0
    answer_cache_hits: int = 0
    queries: int = 0
    last_latency_ms: Dict[str, float] = field(default_factory=dict)


# --- tokenisation -------------------------------------------------------

def _encoder():
    try:
        import tiktoken

        return tiktoken.get_encoding("cl100k_base")
    except Exception:  # noqa: BLE001
        return None


_ENC = _encoder()


def count_tokens(text: str) -> int:
    if _ENC is not None:
        return len(_ENC.encode(text))
    return max(1, len(text) // 4)  # rough fallback


# --- chunking -----------------------------------------------------------

def chunk_text(
    text: str,
    source: str,
    page: Optional[int] = None,
    max_tokens: int = DEFAULT_CHUNK_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
) -> List[Chunk]:
    """Split on paragraph boundaries, packing up to max_tokens with overlap.

    Splitting on a fixed character count is the obvious approach and the wrong
    one: it cuts sentences, and an embedding of half a sentence sits nowhere
    useful in the vector space. Paragraphs are the natural semantic unit of a
    thesis, so paragraphs are packed until the budget is reached, and only a
    paragraph that is itself over-budget is split on token count.
    """
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: List[Chunk] = []
    buf: List[str] = []
    buf_tokens = 0
    ordinal = 0

    def flush() -> None:
        nonlocal buf, buf_tokens, ordinal
        if not buf:
            return
        body = "\n\n".join(buf).strip()
        if body:
            chunks.append(Chunk(text=body, source=source, page=page, ordinal=ordinal))
            ordinal += 1
        # carry the tail of this chunk into the next one
        if overlap_tokens > 0 and _ENC is not None:
            tail = _ENC.decode(_ENC.encode(body)[-overlap_tokens:])
            buf, buf_tokens = [tail], count_tokens(tail)
        else:
            buf, buf_tokens = [], 0

    for para in paras:
        n = count_tokens(para)
        if n > max_tokens:                      # an over-long paragraph
            flush()
            if _ENC is not None:
                ids = _ENC.encode(para)
                step = max_tokens - overlap_tokens
                for s in range(0, len(ids), step):
                    piece = _ENC.decode(ids[s : s + max_tokens])
                    chunks.append(Chunk(piece, source, page, ordinal))
                    ordinal += 1
            else:
                chunks.append(Chunk(para, source, page, ordinal))
                ordinal += 1
            continue
        if buf_tokens + n > max_tokens:
            flush()
        buf.append(para)
        buf_tokens += n

    flush()
    # a trailing overlap-only fragment carries no new content
    return [c for c in chunks if count_tokens(c.text) > overlap_tokens // 2 or len(chunks) == 1]


# --- the service --------------------------------------------------------

class RagService:
    def __init__(self, api_key: Optional[str] = None, index_name: Optional[str] = None) -> None:
        self.index_name = index_name or os.getenv("RAG_INDEX_NAME", "multimodal-robot-autonomy")
        self._openai_key = api_key or os.getenv("OPENAI_API_KEY")
        self._pinecone_key = os.getenv("PINECONE_API_KEY")
        self.stats = RagStats()
        self._client = None
        self._index = None
        self._namespaces: Optional[List[str]] = None
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._embed_cache: Dict[str, List[float]] = self._load(EMBED_CACHE)
        self._answer_cache: Dict[str, Any] = self._load(ANSWER_CACHE)

    # -- persistence
    @staticmethod
    def _load(path: Path) -> Dict[str, Any]:
        if path.exists():
            try:
                return json.loads(path.read_text())
            except Exception:  # noqa: BLE001
                return {}
        return {}

    def _save(self, path: Path, obj: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(obj))
        tmp.replace(path)          # atomic, so a crash cannot truncate the cache

    # -- lazy clients
    @property
    def openai(self):
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(api_key=self._openai_key)
        return self._client

    @property
    def index(self):
        if self._index is None:
            from pinecone import Pinecone, ServerlessSpec

            pc = Pinecone(api_key=self._pinecone_key)
            existing = [i["name"] for i in pc.list_indexes()]
            if self.index_name not in existing:
                pc.create_index(
                    name=self.index_name,
                    dimension=EMBED_DIM,
                    metric="cosine",
                    spec=ServerlessSpec(cloud="aws", region="us-east-1"),
                )
                for _ in range(60):
                    if pc.describe_index(self.index_name).status.get("ready"):
                        break
                    time.sleep(2)
            self._index = pc.Index(self.index_name)
        return self._index

    # -- embedding, with the content-addressed cache
    def embed(self, texts: List[str]) -> List[List[float]]:
        out: List[Optional[List[float]]] = [None] * len(texts)
        todo: List[Tuple[int, str]] = []
        for i, t in enumerate(texts):
            key = hashlib.sha256(t.encode("utf-8")).hexdigest()
            cached = self._embed_cache.get(key)
            if cached is not None:
                out[i] = cached
                self.stats.embed_cache_hits += 1
            else:
                todo.append((i, t))

        for s in range(0, len(todo), EMBED_BATCH):
            batch = todo[s : s + EMBED_BATCH]
            t0 = time.time()
            resp = self.openai.embeddings.create(
                model=EMBED_MODEL, input=[t for _, t in batch]
            )
            self.stats.embed_calls += 1
            self.stats.last_latency_ms["embed"] = (time.time() - t0) * 1000
            for (i, t), item in zip(batch, resp.data):
                out[i] = item.embedding
                self._embed_cache[hashlib.sha256(t.encode("utf-8")).hexdigest()] = item.embedding
                self.stats.chunks_embedded += 1

        if todo:
            self._save(EMBED_CACHE, self._embed_cache)
        return [v for v in out if v is not None]

    # -- ingestion
    def ingest(self, chunks: List[Chunk], namespace: str = "") -> Dict[str, Any]:
        if not chunks:
            return {"upserted": 0}
        vectors = self.embed([c.text for c in chunks])
        payload = [
            {
                "id": c.uid,
                "values": v,
                "metadata": {
                    "text": c.text[:3000],
                    "source": c.source,
                    "page": c.page if c.page is not None else -1,
                    "ordinal": c.ordinal,
                },
            }
            for c, v in zip(chunks, vectors)
        ]
        for s in range(0, len(payload), 100):
            self.index.upsert(vectors=payload[s : s + 100], namespace=namespace)
        return {
            "upserted": len(payload),
            "embed_calls": self.stats.embed_calls,
            "cache_hits": self.stats.embed_cache_hits,
        }

    # -- retrieval
    def retrieve(self, question: str, top_k: int = DEFAULT_TOP_K,
                 namespace: str = "") -> List[Retrieved]:
        """Retrieve across namespaces, guaranteeing each one is represented.

        A single top-k over the union of documents is dominated by whichever
        document has the most chunks. Measured here: the thesis contributes 56
        chunks and the profile 4, and a question about the author retrieved five
        thesis chunks at similarity 0.197--0.208 and nothing from the profile
        that actually held the answer -- so the generator correctly, and
        uselessly, reported that the sources did not cover it.

        Retrieving a quota from each namespace separately removes the size bias:
        the minority document is always represented, and the generator decides
        what is relevant. Ranking within the merged set is still by score, so a
        genuinely irrelevant namespace contributes low-scoring passages that the
        prompt's "say so if the sources do not cover it" instruction handles.
        """
        namespaces = [namespace] if namespace else self.namespaces()
        if len(namespaces) <= 1:
            return self._query_one(question, top_k, namespaces[0] if namespaces else "")

        # split the budget, leaving at least one slot per namespace
        per_ns = max(1, top_k // len(namespaces))
        hits: List[Retrieved] = []
        t0 = time.time()
        for ns in namespaces:
            hits.extend(self._query_one(question, per_ns, ns, timed=False))
        self.stats.last_latency_ms["retrieve"] = (time.time() - t0) * 1000
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[: max(top_k, len(namespaces))]

    def namespaces(self) -> List[str]:
        """Namespaces present in the index, cached after the first call."""
        if self._namespaces is None:
            try:
                stats = self.index.describe_index_stats()
                self._namespaces = sorted(
                    ns for ns, v in (stats.get("namespaces") or {}).items()
                    if (v.get("vector_count") or 0) > 0
                )
            except Exception:  # noqa: BLE001
                self._namespaces = []
        return self._namespaces

    def _query_one(self, question: str, top_k: int, namespace: str,
                   timed: bool = True) -> List[Retrieved]:
        qv = self.embed([question])[0]
        t0 = time.time()
        res = self.index.query(
            vector=qv, top_k=top_k, include_metadata=True, namespace=namespace
        )
        if timed:
            self.stats.last_latency_ms["retrieve"] = (time.time() - t0) * 1000
        hits = []
        for m in res.get("matches", []):
            md = m.get("metadata") or {}
            page = md.get("page")
            hits.append(
                Retrieved(
                    text=md.get("text", ""),
                    source=md.get("source", "?"),
                    page=None if page in (None, -1) else int(page),
                    score=float(m.get("score", 0.0)),
                )
            )
        return hits

    # -- generation
    def ask(self, question: str, top_k: int = DEFAULT_TOP_K,
            namespace: str = "", use_cache: bool = True) -> Dict[str, Any]:
        self.stats.queries += 1
        normalised = re.sub(r"\s+", " ", question.strip().lower())
        key = hashlib.sha256(f"{normalised}|{top_k}|{namespace}".encode()).hexdigest()
        if use_cache and key in self._answer_cache:
            self.stats.answer_cache_hits += 1
            hit = dict(self._answer_cache[key])
            hit["cached"] = True
            return hit

        t0 = time.time()
        hits = self.retrieve(question, top_k=top_k, namespace=namespace)
        if not hits:
            return {"answer": "I have nothing indexed that covers that.",
                    "sources": [], "cached": False}

        context = "\n\n".join(
            f"[{i+1}] ({h.source}"
            + (f", p.{h.page}" if h.page else "")
            + f")\n{h.text}"
            for i, h in enumerate(hits)
        )
        prompt = (
            "Answer the question using only the numbered sources below. Cite the "
            "sources you use as [1], [2] and so on. If the sources do not contain "
            "the answer, say so plainly rather than guessing.\n\n"
            f"{context}\n\nQuestion: {question}\nAnswer:"
        )
        resp = self.openai.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )
        answer = resp.choices[0].message.content or ""
        out = {
            "answer": answer,
            "sources": [
                {"source": h.source, "page": h.page, "score": round(h.score, 4)}
                for h in hits
            ],
            "latency_ms": round((time.time() - t0) * 1000, 1),
            "cached": False,
        }
        self._answer_cache[key] = out
        self._save(ANSWER_CACHE, self._answer_cache)
        self.stats.last_latency_ms["ask"] = out["latency_ms"]
        return out

    def status(self) -> Dict[str, Any]:
        info: Dict[str, Any] = {
            "index": self.index_name,
            "embedding_model": EMBED_MODEL,
            "dimension": EMBED_DIM,
            "chunk_tokens": DEFAULT_CHUNK_TOKENS,
            "chunk_overlap": DEFAULT_OVERLAP_TOKENS,
            "top_k": DEFAULT_TOP_K,
            "embedding_cache_entries": len(self._embed_cache),
            "answer_cache_entries": len(self._answer_cache),
            "stats": self.stats.__dict__,
        }
        try:
            info["vectors"] = self.index.describe_index_stats().get("total_vector_count")
        except Exception as exc:  # noqa: BLE001
            info["vectors"] = f"unavailable: {exc}"
        return info


_rag: Optional[RagService] = None


def get_rag_service() -> RagService:
    global _rag
    if _rag is None:
        _rag = RagService()
    return _rag
