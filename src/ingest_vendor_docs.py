# src/ingest_vendor_docs.py
"""
Unified Vendor Docs Ingester (Spider Edition).
Now crawls 1 level deep to fetch content from Table of Contents / Hub pages.
"""
import os
import bs4
from typing import List, Dict
# Switched from WebBaseLoader to RecursiveUrlLoader for depth capabilities
from langchain_community.document_loaders import RecursiveUrlLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from src.config import (
    VENDOR_DOCS_INDEX_PATH,
    get_embed_model_name,
    LLM_PROVIDER,
    VENDOR_DOCS_URLS
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
    """
    Custom extractor to replicate the 'SoupStrainer' logic.
    We only want the meat of the article, not navbars/sidebars.
    """
    # 1. Define what tags hold the actual documentation content
    #    (Adjusted to catch common doc wrappers like 'article', 'main', 'div[class*="content"]')
    strainer = bs4.SoupStrainer(["article", "main", "div", "p"])
    
    # 2. Parse only those tags
    soup = bs4.BeautifulSoup(html, "html.parser", parse_only=strainer)
    
    # 3. Return clean text
    return soup.get_text(separator=" ", strip=True)

def ingest_docs():
    all_docs = []
    
    # Loop through each vendor in the config
    for vendor, urls in VENDOR_DOCS_URLS.items():
        print(f"🕷️  Crawling {vendor.upper()} (Depth=1)...")
        vendor_docs = []
        
        for url in urls:
            try:
                # RecursiveUrlLoader:
                # max_depth=1 -> Fetches the Root URL + All immediate children links
                # prevent_outside=True -> Ensures we don't crawl the whole internet (stays on domain)
                loader = RecursiveUrlLoader(
                    url=url,
                    max_depth=1, 
                    extractor=smart_extractor,
                    prevent_outside=True,
                    timeout=10
                )
                raw_docs = loader.load()
                vendor_docs.extend(raw_docs)
            except Exception as e:
                print(f"   ⚠️  Skipping {url}: {e}")

        # Deduplicate docs (in case multiple roots linked to the same child)
        unique_urls = set()
        unique_docs = []
        for d in vendor_docs:
            if d.metadata['source'] not in unique_urls:
                unique_urls.add(d.metadata['source'])
                
                # Tag metadata
                d.metadata["platform"] = vendor
                d.metadata["doc_type"] = "vendor_docs"
                # Clean up title
                d.metadata["title"] = d.metadata.get("title", "").replace("\n", " ").strip()
                
                unique_docs.append(d)

        print(f"   ✅ Collected {len(unique_docs)} unique pages for {vendor}.")
        all_docs.extend(unique_docs)

    # Split
    print(f"✂️  Splitting {len(all_docs)} documents...")
    splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=200)
    splits = splitter.split_documents(all_docs)
    
    # Embed & Save
    print(f"🧠 Embedding {len(splits)} chunks into {VENDOR_DOCS_INDEX_PATH}...")
    embeddings = get_embeddings()
    vectorstore = FAISS.from_documents(splits, embeddings)
    vectorstore.save_local(str(VENDOR_DOCS_INDEX_PATH))
    print("✨ Done! Vector Store Updated.")

if __name__ == "__main__":
    ingest_docs()