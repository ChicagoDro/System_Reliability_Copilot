# ingest_runbooks.py
"""
Build a FAISS vector index from curated Platform Runbooks Markdown files.

Expected markdown chunk format (repeat many times per file):

---
## Chunk <CHUNK_ID>
**metadata**
```yaml
chunk_id: ...
platform_id: databricks|snowflake|airflow|...
topic: sla|cost|dq|observability|lineage
applies_to: [ ... ]
severity: low|medium|high
scenario_tags: [ ... ]
signals: [ ... ]
```

**content**
<free-form text ...>
---

This script:
- Recursively loads *.md files under runbooks_dir
- Splits them into chunks
- Parses YAML metadata per chunk
- Embeds each chunk and writes a FAISS index

Modes:
- lite: indexes only Databricks runbooks (fast, minimal)
- demo: indexes all platforms found in runbooks_dir

Usage:
  python ingest_runbooks.py --runbooks_dir runbooks --index_dir indexes --index_name reliability_runbooks_lite --mode lite
  python ingest_runbooks.py --runbooks_dir runbooks --index_dir indexes --index_name reliability_runbooks_demo --mode demo

Embeddings:
- provider=openai uses langchain_openai.OpenAIEmbeddings
- provider=huggingface uses langchain_community.embeddings.HuggingFaceEmbeddings

Environment (optional):
  OPENAI_API_KEY
  OPENAI_EMBEDDING_MODEL (default: text-embedding-3-large)
  HF_EMBEDDING_MODEL (default: sentence-transformers/all-MiniLM-L6-v2)
"""

from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()  # load OPENAI_API_KEY, etc.

import argparse
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml  # type: ignore
except Exception:
    yaml = None

from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS


def get_embeddings(provider: str, model: Optional[str] = None):
    provider = (provider or "").strip().lower()

    if provider in ("openai", "oai"):
        from langchain_openai import OpenAIEmbeddings  # type: ignore

        return OpenAIEmbeddings(model=model or os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large"))

    if provider in ("huggingface", "sentence_transformers", "sbert"):
        from langchain_community.embeddings import HuggingFaceEmbeddings  # type: ignore

        return HuggingFaceEmbeddings(
            model_name=model or os.getenv("HF_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        )

    raise ValueError(f"Unknown embeddings provider: {provider}. Use openai or huggingface.")


_CHUNK_HEADER_RE = re.compile(r"^##\s*Chunk\s+([A-Za-z0-9_\-]+)\s*$", re.MULTILINE)
_YAML_FENCE_RE = re.compile(r"```yaml\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
_CONTENT_MARKER_RE = re.compile(r"^\*\*content\*\*\s*$", re.MULTILINE)


@dataclass
class RunbookChunk:
    chunk_id: str
    metadata: Dict[str, Any]
    content: str
    source_file: str


def _parse_yaml_block(block: str) -> Dict[str, Any]:
    if not block.strip():
        return {}

    if yaml is None:
        out: Dict[str, Any] = {}
        for line in block.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            k, v = line.split(":", 1)
            k = k.strip()
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                inner = v[1:-1].strip()
                out[k] = [x.strip() for x in inner.split(",") if x.strip()] if inner else []
            else:
                out[k] = v
        return out

    try:
        obj = yaml.safe_load(block)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def parse_runbook_markdown(path: Path) -> List[RunbookChunk]:
    text = path.read_text(encoding="utf-8", errors="replace")

    headers = [(m.group(1), m.start()) for m in _CHUNK_HEADER_RE.finditer(text)]
    if not headers:
        return []

    chunks: List[RunbookChunk] = []
    for idx, (chunk_id, start_pos) in enumerate(headers):
        end_pos = headers[idx + 1][1] if idx + 1 < len(headers) else len(text)
        block = text[start_pos:end_pos].strip()

        ym = _YAML_FENCE_RE.search(block)
        yaml_block = ym.group(1) if ym else ""
        meta = _parse_yaml_block(yaml_block)

        cm = _CONTENT_MARKER_RE.search(block)
        if cm:
            content = block[cm.end():].strip()
        else:
            content = _YAML_FENCE_RE.sub("", block).strip()

        meta = dict(meta or {})
        meta.setdefault("chunk_id", chunk_id)

        chunks.append(
            RunbookChunk(
                chunk_id=chunk_id,
                metadata=meta,
                content=content,
                source_file=str(path.as_posix()),
            )
        )

    return chunks


def load_all_runbooks(runbooks_dir: Path) -> List[RunbookChunk]:
    md_files = sorted(runbooks_dir.rglob("*.md"))
    all_chunks: List[RunbookChunk] = []
    for f in md_files:
        all_chunks.extend(parse_runbook_markdown(f))
    return all_chunks


def build_documents(chunks: List[RunbookChunk]) -> List[Document]:
    docs: List[Document] = []
    for c in chunks:
        meta = dict(c.metadata or {})
        meta["source_file"] = c.source_file
        meta["doc_type"] = "runbook"
        meta.setdefault("doc_id", c.chunk_id)

        platform_id = meta.get("platform_id", "unknown")
        topic = meta.get("topic", "unknown")
        severity = meta.get("severity", "unknown")

        page_content = (
            f"[RUNBOOK] platform={platform_id} topic={topic} severity={severity} chunk_id={c.chunk_id}\n\n"
            f"{c.content.strip()}"
        )
        docs.append(Document(page_content=page_content, metadata=meta))
    return docs


def filter_by_mode(chunks: List[RunbookChunk], mode: str) -> List[RunbookChunk]:
    mode = (mode or "").strip().lower()
    if mode == "lite":
        out = []
        for c in chunks:
            pid = (c.metadata or {}).get("platform_id", "")
            if str(pid).lower() == "databricks":
                out.append(c)
        return out
    if mode == "demo":
        return chunks
    raise ValueError("mode must be 'lite' or 'demo'")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runbooks_dir", type=str, default="runbooks")
    ap.add_argument("--index_dir", type=str, default="indexes")
    ap.add_argument("--index_name", type=str, required=True)
    ap.add_argument("--mode", type=str, default="lite", choices=["lite", "demo"])
    ap.add_argument("--provider", type=str, default=os.getenv("EMBEDDINGS_PROVIDER", "openai"))
    ap.add_argument("--model", type=str, default=os.getenv("EMBEDDINGS_MODEL", ""))
    ap.add_argument("--min_chars", type=int, default=80)
    args = ap.parse_args()

    runbooks_dir = Path(args.runbooks_dir).resolve()
    index_dir = Path(args.index_dir).resolve()
    index_path = index_dir / args.index_name

    if not runbooks_dir.exists():
        raise FileNotFoundError(f"runbooks_dir not found: {runbooks_dir}")

    chunks = load_all_runbooks(runbooks_dir)
    chunks = [c for c in chunks if len((c.content or "").strip()) >= args.min_chars]
    chunks = filter_by_mode(chunks, args.mode)

    if not chunks:
        raise RuntimeError(f"No runbook chunks found (mode={args.mode}) under {runbooks_dir}")

    docs = build_documents(chunks)

    embeddings_model = args.model.strip() or None
    embeddings = get_embeddings(args.provider, embeddings_model)

    index_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loaded runbook chunks: {len(chunks)}")
    print(f"Building FAISS index at: {index_path}")

    vstore = FAISS.from_documents(docs, embeddings)
    vstore.save_local(str(index_path))

    platforms = sorted({str((c.metadata or {}).get('platform_id', 'unknown')).lower() for c in chunks})
    topics = sorted({str((c.metadata or {}).get('topic', 'unknown')).lower() for c in chunks})
    print("Done.")
    print(f"Platforms: {platforms}")
    print(f"Topics: {topics}")


if __name__ == "__main__":
    main()
