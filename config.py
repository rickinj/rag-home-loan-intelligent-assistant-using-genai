import os
from dotenv import load_dotenv

load_dotenv()

# --- GOOGLE AUTH ---
# Chat LLM uses Service Account (NOT API KEY)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

# --- LLM MODELS ---
MODEL_NAME = "gemini-2.5-flash"
EMBEDDING_MODEL = "embedding-001"
LLM_TEMPERATURE = 0.1

# --- RAG PDFs ---
PDF_FILES = [
    "docs/pricing-grid.pdf",
    "docs/RBL Bank FAQs.pdf",
    "docs/RBL Bank Loan Credit Policy.pdf",
    "docs/RBL_Bank_Credit_Policy[2].pdf"
]


# --- RAG Settings ---
RAG_CHUNK_SIZE = 1500
RAG_CHUNK_OVERLAP = 200
RAG_TOP_K = 5

# --- OTP ---
MOCK_OTP_CODE = "123456"

# --- BIGQUERY CONFIG (FIX) ---
BIGQUERY_PROJECT_ID = os.getenv("BIGQUERY_PROJECT_ID")
BIGQUERY_DATASET = os.getenv("BIGQUERY_DATASET")
