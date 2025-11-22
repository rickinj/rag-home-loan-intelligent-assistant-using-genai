# rag_processor.py
import os
import streamlit as st
from typing import List

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS

from langchain_google_genai import GoogleGenerativeAIEmbeddings

from google.auth import default
credentials, project = default()

import config


# --- Ensure Service Account Credential is active ---
def _validate_google_credentials():
    cred_path = config.GOOGLE_APPLICATION_CREDENTIALS
    if not cred_path or not os.path.exists(cred_path):
        raise RuntimeError(
            f"❌ GOOGLE_APPLICATION_CREDENTIALS path invalid or missing: {cred_path}\n"
            "Embeddings REQUIRE service account credentials."
        )


@st.cache_resource(show_spinner="Loading RBL knowledge base…")
def load_rag_vector_db():
    """Loads PDFs, splits them, embeds, and builds FAISS store."""
    # Validate credentials
    _validate_google_credentials()

    docs = []
    for pdf in config.PDF_FILES:
        if not os.path.exists(pdf):
            st.warning(f"⚠ PDF missing: {pdf} — skipping.")
            continue

        try:
            loader = PyPDFLoader(pdf)
            pdf_docs = loader.load()
            docs.extend(pdf_docs)
        except Exception as e:
            st.error(f"PDF Load error [{pdf}]: {e}")

    if not docs:
        st.error("❌ No documents loaded for RAG.")
        return None

    # --- Split documents ---
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.RAG_CHUNK_SIZE,
        chunk_overlap=config.RAG_CHUNK_OVERLAP
    )
    split_docs = splitter.split_documents(docs)

    # --- Create Embeddings (SERVICE ACCOUNT ONLY!) ---
    try:
        
        embeddings = GoogleGenerativeAIEmbeddings(
            model=config.EMBEDDING_MODEL,
            credentials=credentials
        )
    except Exception as e:
        st.error(f"❌ Embedding initialization failed: {e}")
        return None

    # --- Build FAISS Vectorstore ---
    try:
        vectorstore = FAISS.from_documents(split_docs, embeddings)
        print("FAISS vector store loaded successfully.")
        return vectorstore
    except Exception as e:
        st.error(f"❌ Failed to build FAISS store: {e}")
        return None


def get_retrieved_context(query: str, vector_db) -> str:
    """Returns combined context for RAG answer generation."""
    if vector_db is None:
        return "Knowledge base unavailable."

    try:
        results = vector_db.similarity_search(query, k=config.RAG_TOP_K)
    except Exception as e:
        return f"RAG retrieval error: {e}"

    if not results:
        return "No relevant context found."

    # Combine
    context_str = "\n\n---\n\n".join(
        [f"[From {os.path.basename(doc.metadata.get('source', ''))}]\n{doc.page_content}"
         for doc in results]
    )
    return context_str
