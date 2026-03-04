# src/RAG_build/ingest_embed_index.py
"""
Embed Reliability Copilot RAG docs and persist a FAISS index.

Vector DB ingestion entrypoint for the Reliability Copilot schema.

Examples:
  python -m src.RAG_build.ingest_embed_index --db-path data/reliability.db --mode lite
  python -m src.RAG_build.ingest_embed_index --db-path data/reliability.db --mode demo --index_name reliability_demo
"""

from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

import argparse
import os
from pathlib import Path
from typing import List, Optional

from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS

from .ingest_reliability_domain import RagDoc, build_reliability_rag_docs
from src.config import get_embed_model_name


# ----------------------------
# Embeddings factory
# ----------------------------

def _get_embeddings(provider: str, model: Optional[str] = None):
    provider = (provider or "").strip().lower()

    if provider in ("openai", "oai"):
        try:
            from langchain_openai import OpenAIEmbeddings  # type: ignore
        except Exception as e:
            raise RuntimeError(
                "OpenAI embeddings selected but langchain_openai is not installed."
            ) from e

        return OpenAIEmbeddings(model=model or get_embed_model_name())

    if provider in ("huggingface", "sentence_transformers", "sbert"):
        try:
            from langchain_community.embeddings import HuggingFaceEmbeddings  # type: ignore
        except Exception as e:
            raise RuntimeError(
                "HuggingFace embeddings selected but dependencies are missing."
            ) from e

        return HuggingFaceEmbeddings(
            model_name=model
            or os.getenv("HF_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        )

    raise ValueError(f"Unknown provider: {provider}. Use openai or huggingface.")


def _to_langchain_docs(rag_docs: List[RagDoc]) -> List[Document]:
    out: List[Document] = []
    for d in rag_docs:
        extra_meta = getattr(d, "metadata", None) or {}
        out.append(
            Document(
                page_content=d.text,
                metadata={"doc_id": d.doc_id, **extra_meta},
            )
        )
    return out


# ----------------------------
# Main
# ----------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Build FAISS vector index for Reliability Copilot RAG docs."
    )
    ap.add_argument("--db-path", required=True, help="Path to reliability SQLite DB.")
    ap.add_argument("--index-dir", default="indexes")
    ap.add_argument("--index_name", default=None)
    ap.add_argument(
        "--provider",
        default=os.getenv("EMBEDDINGS_PROVIDER")
        or os.getenv("LLM_PROVIDER", "openai"),
        help="Embeddings provider: openai|huggingface",
    )
    ap.add_argument("--embed-model", default=None)
    ap.add_argument("--days-back", type=int, default=None)
    ap.add_argument("--clean", action="store_true")
    args = ap.parse_args()

    index_name = args.index_name
    out_dir = Path(args.index_dir) / index_name

    if args.clean and out_dir.exists():
        for p in out_dir.rglob("*"):
            if p.is_file():
                p.unlink()
        for p in sorted(out_dir.rglob("*"), reverse=True):
            if p.is_dir():
                p.rmdir()
        out_dir.rmdir()

    out_dir.mkdir(parents=True, exist_ok=True)

    rag_docs = build_reliability_rag_docs(
        db_path=args.db_path,
        days_back=args.days_back,
    )

    lc_docs = _to_langchain_docs(rag_docs)

    embeddings = _get_embeddings(args.provider, args.embed_model)
    vectorstore = FAISS.from_documents(lc_docs, embeddings)
    vectorstore.save_local(str(out_dir))

    print(f"✅ Built FAISS index '{index_name}' at {out_dir}")
    print(f"   Docs embedded: {len(lc_docs)}")
    print(f"   Provider: {args.provider}")


if __name__ == "__main__":
    main()
