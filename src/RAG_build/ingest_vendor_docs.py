# src/RAG_build/ingest_vendor_docs.py
"""
Vendor Docs Ingester — crawls documentation URLs and indexes into Neo4j vector store.
"""
import os
import bs4
from typing import List

from langchain_community.document_loaders import RecursiveUrlLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Neo4jVector
from langchain_core.documents import Document

from src.config import (
    NEO4J_URI,
    NEO4J_USERNAME,
    NEO4J_PASSWORD,
    NEO4J_DATABASE,
    NEO4J_VENDOR_DOCS_INDEX,
    get_embed_model_name,
    LLM_PROVIDER,
    VENDOR_DOCS_URLS,
)


def get_embeddings():
    provider = (LLM_PROVIDER or "openai").lower()
    model = get_embed_model_name()
    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(model=model)
    if provider == "gemini":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        return GoogleGenerativeAIEmbeddings(model=model)
    raise ValueError(f"Unknown provider: {provider}")


def smart_extractor(html: str) -> str:
    strainer = bs4.SoupStrainer(["article", "main", "div", "p"])
    soup = bs4.BeautifulSoup(html, "html.parser", parse_only=strainer)
    return soup.get_text(separator=" ", strip=True)


def ingest_docs():
    all_docs: List[Document] = []

    for vendor, urls in VENDOR_DOCS_URLS.items():
        print(f"Crawling {vendor.upper()} (depth=1)...")
        vendor_docs: List[Document] = []

        for url in urls:
            try:
                loader = RecursiveUrlLoader(
                    url=url,
                    max_depth=1,
                    extractor=smart_extractor,
                    prevent_outside=True,
                    timeout=10,
                )
                vendor_docs.extend(loader.load())
            except Exception as e:
                print(f"  Skipping {url}: {e}")

        # Deduplicate by source URL
        seen_urls = set()
        for d in vendor_docs:
            src = d.metadata.get("source", "")
            if src not in seen_urls:
                seen_urls.add(src)
                d.metadata["platform"] = vendor
                d.metadata["doc_type"] = "vendor_docs"
                d.metadata["title"] = d.metadata.get("title", "").replace("\n", " ").strip()
                all_docs.append(d)

        print(f"  Collected {len(seen_urls)} unique pages for {vendor}.")

    print(f"Splitting {len(all_docs)} documents...")
    splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=200)
    splits = splitter.split_documents(all_docs)

    print(f"Embedding {len(splits)} chunks into Neo4j index '{NEO4J_VENDOR_DOCS_INDEX}'...")
    embeddings = get_embeddings()

    Neo4jVector.from_documents(
        splits,
        embeddings,
        url=NEO4J_URI,
        username=NEO4J_USERNAME,
        password=NEO4J_PASSWORD,
        database=NEO4J_DATABASE,
        index_name=NEO4J_VENDOR_DOCS_INDEX,
        node_label="VendorDoc",
        text_node_property="text",
        embedding_node_property="embedding",
        pre_delete_collection=True,
    )
    print("Done. Vendor docs indexed in Neo4j.")


if __name__ == "__main__":
    ingest_docs()
