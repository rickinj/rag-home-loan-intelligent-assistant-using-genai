# 🏦 RBL Home Loan Intelligent Assistant 

## 📌 Legal Disclaimer

This project is not affiliated with, endorsed by, or approved by RBL Bank.
The content is sourced from publicly available online documentation for educational purposes only.
Improper or commercial use of this repository is strictly prohibited.

---
 
### AI-powered EMI Calculator • Eligibility Engine • RAG Policy Assistant

This project implements a fully functional **Home Loan Assistant** that can:
- 💰 Calculate EMI with full amortization schedule  
- 📊 Check loan eligibility using FOIR & EMI-based logic  
- 📚 Answer policy questions using RAG (Retrieval-Augmented Generation)  
- 📝 Extract, classify, and store data into BigQuery  
- 🤖 Maintain multi-step dialogue with an intelligent agent  

Built using **Streamlit**, **LangChain**, **Google Gemini**, **FAISS**, and **BigQuery**.

---

## 🚀 Features

### 🔢 1. EMI Calculator
- Collects principal, tenure, and interest rate  
- Validates values intelligently using LLM classification  
- Generates:  
  - Monthly EMI  
  - Total interest  
  - Total payment  
  - Month-wise amortization schedule  

---

### 📊 2. Loan Eligibility (Soft Sanction)
Based on:
- Income  
- Expense  
- Employment Type  
- Age (DOB)  
- FOIR  
- Reverse EMI calculation  
- Max permissible loan tenure  

Outputs:
- Eligible / Not Eligible  
- Soft sanction loan amount  
- Reason  

---

### 🧠 3. RAG Policy Support
- Loads multiple PDFs  
- Splits using text chunker  
- Embeds with **Google Generative AI Embeddings** (service account only)  
- Stores in **FAISS** vector index  
- Provides policy answers grounded in bank documentation  

---

### 🤖 4. Intelligent Multi-Flow Agent
The **agent** handles:
- EMI flow  
- Eligibility flow  
- RAG fallback  
- OTP collection  
- Contact flow  
- Intent detection  
- Natural conversation with memory  

The agent supports restarting EMI/Eligibility from anywhere.

---

### 🗂 5. BigQuery Integration  
Continuously logs:
- Full chat history  
- Extracted user data (name, email, phone, income, etc.)  
- Uses **MERGE UPSERT** to update across the session  

Tables created:
- `tbl_conversation`  
- `tbl_extracted_data`

---

## 🏗 Project Structure

```

project/
│
├── app.py # Streamlit front-end app
│
├── agent.py # Main conversation state machine
│
├── llm_services.py # Gemini & LangChain logic
│
├── rag_processor.py # PDF loading, embedding, FAISS
│
├── utils.py # Helpers: OTP, EMI, sanction, BQ
│
├── prompts.py # Intent, RAG & persona prompts
│
├── config.py # Model + PDF + embedding config
│
├── rag_cleanup.py # Resets BigQuery tables
│
├── intent.json # Intent definition file
│
├── docs/ # RAG documents (pricing grid, policy, etc.)
│
├── .env # Credentials & keys
│
└── README.md

```

---

## ⚙️ Installation

### 1️⃣ Install dependencies ((If FAISS fails on Windows → replace with faiss-cpu): 
```bash
pip install streamlit langchain langchain-google-genai google-auth google-auth-oauthlib google-cloud-bigquery faiss-cpu python-dotenv PyPDF2

```

### 2️⃣ Environment Variables (Create a .env file):
```bash
GOOGLE_API_KEY=
GOOGLE_APPLICATION_CREDENTIALS=service_account.json
BIGQUERY_PROJECT_ID=
BIGQUERY_DATASET=
SENDER_EMAIL=
SENDER_APP_PASSWORD=
COMPANY_NAME=
EMAIL_HOST=
EMAIL_PORT=
```

### ▶️ Running the App
```bash
streamlit run app.py
```
## 🧪 Flows Supported
✔ EMI Flow
   - User → Principal → Tenure → ROI → EMI Summary → Eligibility? <br>
   
✔ Eligibility Flow
   - Income → Expense → Job Type → DOB → Pincode → Loan Type → Name → Phone → Email → OTP → Result <br>
   
✔ RAG Flow
   - Any policy question → PDF-backed response
  
---

## 📦 BigQuery Table Schemas

### **1. `tbl_conversation`**

| Column        | Type     |
|---------------|----------|
| session_id    | INT64    |
| conversation  | STRING   |
| time_stamp    | DATETIME |

---

### **2. `tbl_extracted_data`**

| Column        | Type     |
|---------------|----------|
| session_id    | INT64    |
| customer_name | STRING   |
| email         | STRING   |
| phone_number  | STRING   |
| extracted_data| STRING   |

---

## 💡 Highlights / Advantages

- Multi-step agent with memory  
- Flow-safe input validation (LLM + regex fallback)  
- Hybrid RAG + reasoning model  
- Fully structured BigQuery logging  
- Clean integration with Streamlit UI  
- Modular and easy to extend  

---

## 🤝 Contributions

PRs and improvements are welcome.

