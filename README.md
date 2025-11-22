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
# 🔐 Environment Setup (Important)

This project requires two sensitive credentials:

✔ `GOOGLE_APPLICATION_CREDENTIALS`  
✔ `SENDER_APP_PASSWORD`  

Because these contain confidential information, **do NOT upload them to GitHub**.  
Each contributor must create their own credentials by following the steps below.

# 1️⃣ Generate `GOOGLE_APPLICATION_CREDENTIALS`

This is the path to your **Google Cloud Service Account JSON key**, used for BigQuery and Google Cloud authentication.

### **Steps**

1. Go to **Google Cloud Console**  
   https://console.cloud.google.com/

2. Select your project 

3. Open the sidebar → **IAM & Admin → Service Accounts**

4. Click **Create Service Account**

5. Enter a name, e.g.:

6. Click **Create and Continue**

7. Assign these roles:

- **BigQuery Data Viewer**  
- **BigQuery Data Editor**  
- **BigQuery Job User**

8. Click **Continue → Done**

9. Open the created account → go to the **Keys** tab

10. Click **Add Key → Create New Key**

11. Choose **JSON**, then download the file.

12. Place it inside your project.

13. Add this into your `.env`: GOOGLE_APPLICATION_CREDENTIALS=path/to/service_account.json

# 2️⃣ Generate `SENDER_APP_PASSWORD` (Gmail App Password)

This password is required for sending OTP emails from your Gmail account.

### **Steps**

1. Open your Google Security settings:  
https://myaccount.google.com/security

2. Under **Signing in to Google**, enable:
- **2-Step Verification**

3. After that, open App Passwords:  
https://myaccount.google.com/apppasswords

4. Choose:
- **App:** Mail  
- **Device:** Your device (e.g., Windows Computer)

5. Click **Generate**

6. Copy the 16-character password (Google shows it once)

7. Add it to your `.env`: SENDER_APP_PASSWORD=your_generated_app_password.

8. **Never commit this password to GitHub.**

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

