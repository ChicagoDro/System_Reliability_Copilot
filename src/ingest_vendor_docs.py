# src/ingest_vendor_docs.py
"""
Unified Vendor Docs Ingester.
Scrapes specific high-value documentation pages for K8s, Snowflake, Airflow, dbt, and Databricks.
"""
import os
import bs4
from typing import List, Dict
from langchain_community.document_loaders import WebBaseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from src.config import (
    VENDOR_DOCS_INDEX_PATH,
    get_embed_model_name,
    LLM_PROVIDER,
    VENDOR_DOCS_URLS  # <--- Imported from config
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

def ingest_docs():
    all_docs = []
    
    # Use the dictionary imported from config.py
    for vendor, urls in VENDOR_DOCS_URLS.items():
        print(f"📥 Fetching {len(urls)} pages for {vendor.upper()}...")
        try:
            # Custom parsing to remove navbars/footers helps reduce noise
            loader = WebBaseLoader(
                web_paths=urls,
                bs_kwargs=dict(parse_only=bs4.SoupStrainer(["article", "main", "div", "p"]))
            )
            raw_docs = loader.load()
            
            # Tag them with metadata
            for d in raw_docs:
                d.metadata["platform"] = vendor
                d.metadata["doc_type"] = "vendor_docs"
                # Clean up title if possible
                d.metadata["title"] = d.metadata.get("title", "").replace("\n", " ").strip()
                
            all_docs.extend(raw_docs)
            print(f"   ✅ Loaded {len(raw_docs)} pages.")
        except Exception as e:
            print(f"   ❌ Failed to load {vendor}: {e}")

    # Split
    print(f"✂️  Splitting {len(all_docs)} documents...")
    splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=200)
    splits = splitter.split_documents(all_docs)
    
    # Embed & Save
    print(f"🧠 Embedding {len(splits)} chunks into {VENDOR_DOCS_INDEX_PATH}...")
    embeddings = get_embeddings()
    vectorstore = FAISS.from_documents(splits, embeddings)
    vectorstore.save_local(str(VENDOR_DOCS_INDEX_PATH))
    print("✨ Done!")

if __name__ == "__main__":
    ingest_docs()