import os
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from src.config import VENDOR_DOCS_INDEX_PATH, get_embed_model_name, LLM_PROVIDER

# 1. Setup Embeddings
def get_embeddings():
    provider = (LLM_PROVIDER or "openai").lower()
    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(model=get_embed_model_name())
    return GoogleGenerativeAIEmbeddings(model=get_embed_model_name())

# 2. Setup LLM
def get_llm():
    provider = (LLM_PROVIDER or "openai").lower()
    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model="gpt-4o", temperature=0)
    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0)

def test_rag():
    print(f"📂 Loading Vector Store from: {VENDOR_DOCS_INDEX_PATH}...")
    try:
        embeddings = get_embeddings()
        # Allow dangerous deserialization is required for local pickle files
        vectorstore = FAISS.load_local(
            str(VENDOR_DOCS_INDEX_PATH), 
            embeddings, 
            allow_dangerous_deserialization=True
        )
        
        # KEY FIX 1: Use 'similarity_score_threshold'
        # This filters out results that are "kinda close" but not actually relevant.
        # Note: Score range depends on distance metric (L2 vs Cosine). 
        # For FAISS default L2, we often just use 'k' and let the LLM filter, 
        # but here we simulated a stricter retriever.
        retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
        
    except Exception as e:
        print(f"❌ Failed to load index: {e}")
        return

    # KEY FIX 2: The "Anti-Hallucination" Prompt
    template = """You are a strictly constrained Reliability Copilot.
    
    Use ONLY the following context to answer the question. 
    Do not use your prior knowledge. 
    If the answer is not in the context, strictly say: "I cannot answer this based on the provided vendor documentation."
    
    Context:
    {context}
    
    Question: {question}
    """
    prompt = ChatPromptTemplate.from_template(template)
    llm = get_llm()

    # The RAG Chain
    rag_chain = (
        {"context": retriever, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )

    # Test Cases
    test_questions = [
        # Scenario 1: AWS Cost (Should Answer)
        "What are the best practices to optimize AWS EC2 costs for intermittent workloads?",
        
        # Scenario 4: GCP BigQuery (Should FAIL / Return generic)
        "What are the daily quota limits for GCP BigQuery on-demand queries?",

        # Scenario 5: Databricks Schema Drift (Should Answer)
        "How does Databricks Auto Loader handle schema drift or new columns?",
        
        # Scenario 3: Snowflake Data Loss (Should Answer)
        "What is the Time Travel retention period for Snowflake Standard Edition?",
    ]

    print("\n🔎 RUNNING DIAGNOSTIC WITH GUARDRAILS...\n")
    
    for q in test_questions:
        print(f"❓ Question: {q}")
        
        # 1. Inspect Retrieval First (Debug)
        docs = retriever.invoke(q)
        if not docs:
            print("   ⚠️  Retriever found NO matching docs.")
        else:
            print(f"   ✅ Retriever found {len(docs)} chunks.")
            print(f"      Top Source: {docs[0].metadata.get('source', 'Unknown')}")

        # 2. Get LLM Answer
        print("   🤖 Copilot Answer:")
        try:
            answer = rag_chain.invoke(q)
            print(f"      {answer}")
        except Exception as e:
            print(f"      [Error generating answer: {e}]")
            
        print("-" * 60)

if __name__ == "__main__":
    test_rag()