"""src/ingest_databricks_docs.py

Build a *separate* FAISS index containing Databricks vendor documentation
for AWS Compute.

Why separate?
- Your telemetry/usage corpus answers: "what happened in *my* environment?"
- Vendor docs answer: "what does this setting mean / how do I configure it?"

This script:
1) Fetches the Databricks AWS docs sitemap
2) Filters to URLs under /aws/en/compute/
3) Downloads and cleans page text
4) Chunks into LangChain Documents with URL/title metadata
5) Embeds + saves a FAISS index to VENDOR_DOCS_INDEX_PATH

Run:
    python -m src.ingest_databricks_docs
"""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from typing import Iterable, List, Tuple

import requests
from bs4 import BeautifulSoup

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS

from src.config import (
    LLM_PROVIDER,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    DOCS_SITEMAP_URL,
    DOCS_URL_PREFIX,
    VENDOR_DOCS_INDEX_PATH,
    get_embed_model_name,
)


# ---------------------------------------------------------------------------
# Embedding provider routing (mirrors ingest_embed_index.py)
# ---------------------------------------------------------------------------

def get_embeddings():
    provider = (LLM_PROVIDER or "openai").lower()
    model_name = get_embed_model_name()

    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(model=model_name)

    if provider == "gemini":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        return GoogleGenerativeAIEmbeddings(model=model_name)

    if provider == "grok":
        raise NotImplementedError(
            "Grok embeddings are not wired up yet. "
            "Set LLM_PROVIDER=openai or gemini to build the docs index."
        )

    raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")


# ---------------------------------------------------------------------------
# Sitemap + page extraction
# ---------------------------------------------------------------------------

def _fetch_text(url: str, timeout: int = 30) -> str:
    headers = {
        "User-Agent": "ReliabilityCopilot/1.0 (+local ingestion for RAG indexing)"
    }
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.text


def _parse_sitemap_urls(sitemap_xml: str) -> List[str]:
    root = ET.fromstring(sitemap_xml)
    urls = []
    for loc in root.iter():
        if loc.tag.endswith("loc") and loc.text:
            urls.append(loc.text.strip())
    return urls


def _filter_compute_urls(urls: Iterable[str]) -> List[str]:
    prefix = DOCS_URL_PREFIX.rstrip("/") + "/"
    keep = []
    for u in urls:
        if u.startswith(prefix) or u.rstrip("/") == DOCS_URL_PREFIX.rstrip("/"):
            keep.append(u)
    return sorted(set(keep))


def _clean_html_to_text(html: str) -> Tuple[str, str]:
    """Return (title, main_text) from a docs HTML page."""
    soup = BeautifulSoup(html, "html.parser")

    title = ""
    if soup.title and soup.title.get_text(strip=True):
        title = soup.title.get_text(strip=True)

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    for tag in soup.find_all(["header", "footer", "nav", "aside"]):
        tag.decompose()

    main = soup.find("main")
    container = main if main else soup.body if soup.body else soup

    text = container.get_text(separator="\n", strip=True)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    cleaned = []
    for ln in lines:
        if len(ln) <= 1:
            continue
        cleaned.append(ln)

    return title, "\n".join(cleaned)


def _build_docs_documents(urls: List[str], sleep_s: float = 0.75) -> List[Document]:
    docs: List[Document] = []
    for i, url in enumerate(urls, start=1):
        try:
            html = _fetch_text(url)
            title, text = _clean_html_to_text(html)
            if not text or len(text) < 200:
                continue

            docs.append(
                Document(
                    page_content=text,
                    metadata={
                        "source": "databricks_docs",
                        "doc_type": "databricks_docs",
                        "topic": "compute",
                        "platform": "aws",
                        "url": url,
                        "title": title or "Databricks Docs",
                    },
                )
            )
            time.sleep(sleep_s)

        except Exception as e:
            print(f"[docs_ingest] WARN: failed to fetch/parse {url}: {e}")
            continue

        if i % 25 == 0:
            print(f"[docs_ingest] Fetched {i}/{len(urls)} pages...")

    return docs


def _chunk_documents(docs: List[Document]) -> List[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    chunked: List[Document] = []
    for d in docs:
        for c in splitter.split_text(d.page_content):
            chunked.append(Document(page_content=c, metadata=d.metadata))
    return chunked


def main() -> None:
    print("[docs_ingest] Building Databricks docs index")
    print(f"[docs_ingest] Sitemap: {DOCS_SITEMAP_URL}")
    print(f"[docs_ingest] Prefix:  {DOCS_URL_PREFIX}")
    print(f"[docs_ingest] Output:  {VENDOR_DOCS_INDEX_PATH}")
    print(f"[docs_ingest] Provider: {LLM_PROVIDER} | Embed model: {get_embed_model_name()}")

    sitemap_xml = _fetch_text(DOCS_SITEMAP_URL)
    urls = _parse_sitemap_urls(sitemap_xml)
    compute_urls = _filter_compute_urls(urls)

    if not compute_urls:
        raise RuntimeError("No URLs found for the compute docs prefix. Check DOCS_URL_PREFIX.")

    print(f"[docs_ingest] Found {len(compute_urls)} compute docs pages")

    raw_docs = _build_docs_documents(compute_urls)
    print(f"[docs_ingest] Parsed {len(raw_docs)} docs pages into Documents")

    chunked = _chunk_documents(raw_docs)
    print(f"[docs_ingest] Chunked into {len(chunked)} total doc chunks")

    if not chunked:
        raise RuntimeError("No doc chunks produced. Aborting.")

    embeddings = get_embeddings()
    vs = FAISS.from_documents(chunked, embeddings)

    VENDOR_DOCS_INDEX_PATH.mkdir(parents=True, exist_ok=True)
    vs.save_local(str(VENDOR_DOCS_INDEX_PATH))
    print("[docs_ingest] ✅ Saved docs FAISS index")


if __name__ == "__main__":
    main()
