"""Vector storage behind one interface, so the retrieval result does not depend
on which store is running.

The project originally used Pinecone. That is a managed service: the index
lives on someone else's machine, under an account key, in a state nobody else
can reconstruct. For a result that is meant to be reproducible from the
repository alone, that is a hole -- an examiner cannot re-run retrieval without
credentials, and the index can be changed or deleted independently of the work
that cites it.

Chroma stores the index as a directory. It ships with the repository, needs no
key and no network, and reproduces offline. It is also the only option if the
retrieval ever has to run on the robot rather than beside it.

Both are kept, behind this interface, because "the answer does not depend on
the store" is a claim worth being able to demonstrate rather than assert.

    RAG_STORE=chroma    (default) local, on-disk, reproducible
    RAG_STORE=pinecone  managed, for comparison

One asymmetry has to be normalised here rather than left to callers. Pinecone
returns a similarity, where larger is better. Chroma returns a distance, where
smaller is better. The retrieval code ranks and applies per-namespace quotas by
sorting on score descending, so a raw distance passed through unchanged would
silently invert the ranking and return the least relevant passages first. Both
adapters therefore emit a similarity.
"""
from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

# Where a local index lives. Kept beside the other caches so the whole
# retrieval state is one directory.
CHROMA_DIR = Path(
    os.getenv("CHROMA_DIR",
              str(Path(__file__).resolve().parents[2] / "data" / "chroma"))
)

DEFAULT_NAMESPACE = "default"


class VectorStore(Protocol):
    """What the retrieval service needs, and nothing else."""

    def upsert(self, records: List[Dict[str, Any]], namespace: str = "") -> int: ...

    def query(self, vector: List[float], top_k: int,
              namespace: str = "") -> List[Dict[str, Any]]: ...

    def namespaces(self) -> List[str]: ...

    def count(self) -> int: ...

    @property
    def kind(self) -> str: ...


def _ns(namespace: str) -> str:
    return namespace or DEFAULT_NAMESPACE


# --------------------------------------------------------------------------
# Chroma
# --------------------------------------------------------------------------

class ChromaStore:
    """On-disk Chroma. One collection per namespace.

    Chroma has no namespace concept, so a namespace becomes a collection. That
    is preferable to a metadata filter because it keeps per-namespace counts
    exact -- the retrieval code needs to know which namespaces hold anything in
    order to split its budget between them, and a filtered count over one large
    collection is both slower and easier to get wrong.
    """

    def __init__(self, index_name: str, dim: int, path: Optional[Path] = None) -> None:
        self.index_name = index_name
        self.dim = dim
        self.path = Path(path or CHROMA_DIR)
        self.path.mkdir(parents=True, exist_ok=True)
        self._client = None
        self._collections: Dict[str, Any] = {}

    @property
    def kind(self) -> str:
        return "chroma"

    @property
    def client(self):
        if self._client is None:
            import chromadb

            # Telemetry off: this is a measurement instrument, and it should not
            # emit anything of its own over the network.
            from chromadb.config import Settings

            self._client = chromadb.PersistentClient(
                path=str(self.path),
                settings=Settings(anonymized_telemetry=False),
            )
        return self._client

    def _name(self, namespace: str) -> str:
        """Collection name for a namespace.

        Chroma requires 3-63 characters of [a-zA-Z0-9._-], starting and ending
        alphanumeric, so the namespace cannot be used verbatim.
        """
        raw = f"{self.index_name}-{_ns(namespace)}"
        safe = re.sub(r"[^a-zA-Z0-9._-]", "-", raw).strip("-._")
        safe = re.sub(r"-{2,}", "-", safe)
        if len(safe) < 3:
            safe = f"ns-{safe}"
        return safe[:63].rstrip("-._")

    def _collection(self, namespace: str):
        key = self._name(namespace)
        if key not in self._collections:
            self._collections[key] = self.client.get_or_create_collection(
                name=key,
                # Cosine, to match the metric the embeddings were built for and
                # the metric the Pinecone index used.
                metadata={"hnsw:space": "cosine"},
            )
        return self._collections[key]

    def upsert(self, records: List[Dict[str, Any]], namespace: str = "") -> int:
        if not records:
            return 0
        col = self._collection(namespace)
        col.upsert(
            ids=[r["id"] for r in records],
            embeddings=[r["values"] for r in records],
            metadatas=[r.get("metadata") or {} for r in records],
            documents=[(r.get("metadata") or {}).get("text", "") for r in records],
        )
        return len(records)

    def query(self, vector: List[float], top_k: int,
              namespace: str = "") -> List[Dict[str, Any]]:
        col = self._collection(namespace)
        n = col.count()
        if n == 0:
            return []
        res = col.query(
            query_embeddings=[vector],
            n_results=min(top_k, n),
            include=["metadatas", "distances"],
        )
        ids = (res.get("ids") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        out = []
        for i, mid in enumerate(ids):
            d = dists[i] if i < len(dists) else None
            # cosine distance -> cosine similarity, so that larger is better and
            # the caller's descending sort means what it means for Pinecone.
            score = 1.0 - float(d) if d is not None else 0.0
            out.append({
                "id": mid,
                "score": score,
                "metadata": metas[i] if i < len(metas) else {},
            })
        return out

    def namespaces(self) -> List[str]:
        prefix = f"{self.index_name}-"
        found = []
        for col in self.client.list_collections():
            name = col if isinstance(col, str) else col.name
            if not name.startswith(prefix):
                continue
            if self.client.get_collection(name).count() == 0:
                continue
            ns = name[len(prefix):]
            found.append("" if ns == DEFAULT_NAMESPACE else ns)
        return sorted(found)

    def count(self) -> int:
        prefix = f"{self.index_name}-"
        total = 0
        for col in self.client.list_collections():
            name = col if isinstance(col, str) else col.name
            if name.startswith(prefix):
                total += self.client.get_collection(name).count()
        return total


# --------------------------------------------------------------------------
# Pinecone
# --------------------------------------------------------------------------

class PineconeStore:
    """The original managed store, retained so the two can be compared."""

    def __init__(self, index_name: str, dim: int, api_key: Optional[str] = None) -> None:
        self.index_name = index_name
        self.dim = dim
        self._key = api_key or os.getenv("PINECONE_API_KEY")
        self._index = None

    @property
    def kind(self) -> str:
        return "pinecone"

    @property
    def index(self):
        if self._index is None:
            from pinecone import Pinecone, ServerlessSpec

            pc = Pinecone(api_key=self._key)
            existing = [i["name"] for i in pc.list_indexes()]
            if self.index_name not in existing:
                pc.create_index(
                    name=self.index_name, dimension=self.dim, metric="cosine",
                    spec=ServerlessSpec(cloud="aws", region="us-east-1"),
                )
                for _ in range(60):
                    if pc.describe_index(self.index_name).status.get("ready"):
                        break
                    time.sleep(2)
            self._index = pc.Index(self.index_name)
        return self._index

    def upsert(self, records: List[Dict[str, Any]], namespace: str = "") -> int:
        for s in range(0, len(records), 100):
            self.index.upsert(vectors=records[s : s + 100], namespace=namespace)
        return len(records)

    def query(self, vector: List[float], top_k: int,
              namespace: str = "") -> List[Dict[str, Any]]:
        res = self.index.query(vector=vector, top_k=top_k,
                               include_metadata=True, namespace=namespace)
        return [
            {"id": m.get("id"), "score": float(m.get("score", 0.0)),
             "metadata": m.get("metadata") or {}}
            for m in res.get("matches", [])
        ]

    def namespaces(self) -> List[str]:
        try:
            stats = self.index.describe_index_stats()
            return sorted(
                ns for ns, v in (stats.get("namespaces") or {}).items()
                if (v.get("vector_count") or 0) > 0
            )
        except Exception:  # noqa: BLE001
            return []

    def count(self) -> int:
        try:
            return int(self.index.describe_index_stats().get("total_vector_count") or 0)
        except Exception:  # noqa: BLE001
            return 0


def make_store(index_name: str, dim: int, kind: Optional[str] = None) -> VectorStore:
    kind = (kind or os.getenv("RAG_STORE", "chroma")).strip().lower()
    if kind == "pinecone":
        return PineconeStore(index_name, dim)
    return ChromaStore(index_name, dim)
