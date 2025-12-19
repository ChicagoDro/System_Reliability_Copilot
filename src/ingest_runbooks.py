# src/ingest_runbooks.py
"""
Build a FAISS vector index from all Runbooks in the runbooks directory.
"""
from __future__ import annotations
from dotenv import load_dotenv
load_dotenv()

import argparse
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml
except Exception:
    yaml = None

from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS

def get_embeddings(provider: str, model: Optional[str] = None):
    provider = (provider or "").strip().lower()
    if provider in ("openai", "oai"):
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(model=model or os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large"))
    if provider in ("gemini", "google"):
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        return GoogleGenerativeAIEmbeddings(model=model or os.getenv("GEMINI_EMBEDDING_MODEL", "models/text-embedding-004"))
    raise ValueError(f"Unknown embeddings provider: {provider}")

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
    if not block.strip(): return {}
    try:
        return yaml.safe_load(block) if yaml else {}
    except: return {}

def parse_runbook_markdown(path: Path) -> List[RunbookChunk]:
    text = path.read_text(encoding="utf-8", errors="replace")
    headers = [(m.group(1), m.start()) for m in _CHUNK_HEADER_RE.finditer(text)]
    if not headers: return []

    chunks = []
    for idx, (chunk_id, start_pos) in enumerate(headers):
        end_pos = headers[idx + 1][1] if idx + 1 < len(headers) else len(text)
        block = text[start_pos:end_pos].strip()
        
        ym = _YAML_FENCE_RE.search(block)
        meta = _parse_yaml_block(ym.group(1)) if ym else {}
        
        cm = _CONTENT_MARKER_RE.search(block)
        content = block[cm.end():].strip() if cm else _YAML_FENCE_RE.sub("", block).strip()
        
        meta = dict(meta or {})
        meta.setdefault("chunk_id", chunk_id)
        chunks.append(RunbookChunk(chunk_id, meta, content, str(path.as_posix())))
    return chunks

def load_all_runbooks(runbooks_dir: Path) -> List[RunbookChunk]:
    return [c for f in sorted(runbooks_dir.rglob("*.md")) for c in parse_runbook_markdown(f)]

def build_documents(chunks: List[RunbookChunk]) -> List[Document]:
    docs = []
    for c in chunks:
        meta = dict(c.metadata or {})
        meta.update({"source_file": c.source_file, "doc_type": "runbook", "doc_id": c.chunk_id})
        
        # Denormalize key fields for search
        header = f"[RUNBOOK] platform={meta.get('platform_id')} topic={meta.get('topic')} id={c.chunk_id}"
        docs.append(Document(page_content=f"{header}\n\n{c.content}", metadata=meta))
    return docs

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runbooks_dir", type=str, default="src/runbooks")
    ap.add_argument("--index_dir", type=str, default="indexes")
    ap.add_argument("--index_name", type=str, required=True)
    # Removed --mode argument
    args = ap.parse_args()

    runbooks_dir = Path(args.runbooks_dir).resolve()
    index_path = Path(args.index_dir).resolve() / args.index_name

    chunks = load_all_runbooks(runbooks_dir)
    if not chunks:
        raise RuntimeError(f"No runbook chunks found in {runbooks_dir}")

    docs = build_documents(chunks)
    embeddings = get_embeddings(os.getenv("LLM_PROVIDER", "openai"))
    
    print(f"Building FAISS index with {len(docs)} chunks...")
    vstore = FAISS.from_documents(docs, embeddings)
    vstore.save_local(str(index_path))
    print(f"✅ Saved to {index_path}")

if __name__ == "__main__":
    main()