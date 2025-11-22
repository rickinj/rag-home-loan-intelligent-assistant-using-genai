import re
import json
from typing import Dict, Any, List
import streamlit as st
import datetime
from google.cloud import bigquery
import config
import random
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


# ============================================================
# 🔢 INDIAN NUMBER FORMATTER
# ============================================================
def format_indian_style(number: float) -> str:
    s = str(int(number))
    if len(s) <= 3:
        return s

    last_three = s[-3:]
    remaining = s[:-3]
    formatted_remaining = ""

    while remaining:
        if len(remaining) > 2:
            formatted_remaining = remaining[-2:] + ',' + formatted_remaining
            remaining = remaining[:-2]
        else:
            formatted_remaining = remaining + ',' + formatted_remaining
            remaining = ""

    return formatted_remaining.rstrip(',') + ',' + last_three


# ============================================================
# 🔍 NUMERIC PARSER
# ============================================================
def parse_number_from_string(text: str) -> float | None:
    if not isinstance(text, str):
        return None

    s = text.lower().strip()
    s = s.replace(",", "")
    s = s.replace("₹", "")
    s = re.sub(r"\b(rs|inr)\b", "", s)

    m = re.search(r"(-?\d+(?:\.\d+)?)", s)
    if not m:
        return None
    try:
        value = float(m.group(1))
    except Exception:
        return None

    if re.search(r"\b(lakh|lakhs|lac|lacs|l)\b", s):
        return value * 100000
    if re.search(r"\b(crore|crores|cr)\b", s):
        return value * 10000000
    if re.search(r"\bk\b", s) and not re.search(r"\b(ok|km)\b", s):
        return value * 1000

    return value


# ============================================================
# --- OTP GENERATION (SMS STYLE)
# ============================================================
def generate_otp() -> str:
    return f"{random.randint(100000, 999999)}"


def send_fake_otp_to_user(phone_number: str, otp_code: str):
    # For debugging only – prints to console
    print(f"\n📩 DEBUG: Sending OTP {otp_code} to {phone_number}\n")
    return True


def verify_otp(user_input: str, actual_otp: str) -> bool:
    return user_input.strip() == actual_otp.strip()


# ============================================================
# 🆔 4-DIGIT SESSION ID
# ============================================================
def get_session_id() -> str:
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(random.randint(1000, 9999))
    return st.session_state.session_id


# ============================================================
# INT64 CONVERTER
# ============================================================
def _convert_session_to_int(session_id: str) -> int:
    return int(session_id)


# ============================================================
# 🗄️ SAVE TO BIGQUERY  (CONTINUOUS + UPSERT)
# ============================================================
def save_to_bigquery(
    session_id: str,
    chat_history: List[Dict[str, Any]],
    app_state: Dict[str, Any]
):
    """
    Continuous logging:
    - Called after EVERY message.
    - Uses MERGE to UPSERT into BigQuery.
    - One row per session_id in each table.
    - 'conversation' column always holds full chat_history JSON.
    """

    client = bigquery.Client(project=config.BIGQUERY_PROJECT_ID)
    dataset = config.BIGQUERY_DATASET

    tbl_conv = f"{dataset}.tbl_conversation"
    tbl_extract = f"{dataset}.tbl_extracted_data"

    session_int = _convert_session_to_int(session_id)

    # Full chat history JSON (assistant + user messages)
    conversation_json = json.dumps(chat_history, indent=2, ensure_ascii=False)

    # Extracted data JSON payload
    extracted_payload = {
        "pin_code": app_state.get("pin_code"),
        "expense": app_state.get("expense"),
        "income": app_state.get("income"),
        "employment_type": app_state.get("employment_type"),
        "dob": app_state.get("dob"),
        "loan_type": app_state.get("loan_type"),
        "customer_name": app_state.get("customer_name"),
        "email": app_state.get("email"),
        "phone_number": app_state.get("phone"),
    }
    extracted_data_json = json.dumps(extracted_payload, ensure_ascii=False)

    # --------------------------------------------------------
    # 1) UPSERT CONVERSATION TABLE
    #    - time_stamp column is DATETIME in your schema
    # --------------------------------------------------------
    query1 = f"""
    MERGE `{tbl_conv}` T
    USING (
      SELECT
        @session_id AS session_id,
        @conversation AS conversation,
        CURRENT_DATETIME() AS time_stamp
    ) S
    ON T.session_id = S.session_id
    WHEN MATCHED THEN
      UPDATE SET
        T.conversation = S.conversation,
        T.time_stamp = S.time_stamp
    WHEN NOT MATCHED THEN
      INSERT (session_id, conversation, time_stamp)
      VALUES (S.session_id, S.conversation, S.time_stamp)
    """

    job_config1 = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("session_id", "INT64", session_int),
            bigquery.ScalarQueryParameter("conversation", "STRING", conversation_json),
        ]
    )

    client.query(query1, job_config=job_config1).result()
    print("✅ Conversation UPSERTED to BigQuery")

    # --------------------------------------------------------
    # 2) UPSERT EXTRACTED DATA TABLE
    #    - keeps latest customer_name/email/phone/extracted_data
    # --------------------------------------------------------
    query2 = f"""
    MERGE `{tbl_extract}` T
    USING (
      SELECT
        @session_id AS session_id,
        @customer_name AS customer_name,
        @email AS email,
        @phone AS phone_number,
        @extracted AS extracted_data
    ) S
    ON T.session_id = S.session_id
    WHEN MATCHED THEN
      UPDATE SET
        T.customer_name = S.customer_name,
        T.email = S.email,
        T.phone_number = S.phone_number,
        T.extracted_data = S.extracted_data
    WHEN NOT MATCHED THEN
      INSERT (session_id, customer_name, email, phone_number, extracted_data)
      VALUES (S.session_id, S.customer_name, S.email, S.phone_number, S.extracted_data)
    """

    job_config2 = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("session_id", "INT64", session_int),
            bigquery.ScalarQueryParameter(
                "customer_name", "STRING", app_state.get("customer_name")
            ),
            bigquery.ScalarQueryParameter(
                "email", "STRING", app_state.get("email")
            ),
            bigquery.ScalarQueryParameter(
                "phone", "STRING", app_state.get("phone")
            ),
            bigquery.ScalarQueryParameter(
                "extracted", "STRING", extracted_data_json
            ),
        ]
    )

    client.query(query2, job_config=job_config2).result()
    print("✅ Extracted data UPSERTED to BigQuery")


# ============================================================
# EMI SCHEDULE
# ============================================================
def compute_emi_schedule(principal: float, annual_rate_percent: float, tenure_years: int) -> dict:
    if principal is None or annual_rate_percent is None or tenure_years is None:
        return {"error": "Invalid inputs"}

    try:
        P = float(principal)
        annual_rate = float(annual_rate_percent)
        years = int(tenure_years)
    except Exception as e:
        return {"error": str(e)}

    r = annual_rate / 100 / 12
    n = years * 12
    if n <= 0:
        return {"error": "Tenure must be >= 1"}

    if r == 0:
        monthly_emi = P / n
    else:
        pow_val = (1 + r) ** n
        monthly_emi = P * r * pow_val / (pow_val - 1)

    monthly_emi_round = round(monthly_emi, 2)

    schedule = []
    remaining = P
    total_interest, total_payment = 0, 0

    for month in range(1, n + 1):
        interest = remaining * r
        principal_component = monthly_emi - interest
        if principal_component > remaining:
            principal_component = remaining
            payment = principal_component + interest
        else:
            payment = monthly_emi

        remaining -= principal_component
        if remaining < 1e-8:
            remaining = 0.0

        total_interest += interest
        total_payment += payment

        schedule.append({
            "month": month,
            "emi": round(payment, 2),
            "principal_component": round(principal_component, 2),
            "interest_component": round(interest, 2),
            "remaining_principal": round(remaining, 2)
        })

    if schedule:
        schedule[-1]["remaining_principal"] = 0.0

    return {
        "principal": round(P, 2),
        "annual_rate_percent": annual_rate,
        "tenure_years": years,
        "monthly_emi": monthly_emi_round,
        "total_payment": round(total_payment, 2),
        "total_interest": round(total_interest, 2),
        "schedule": schedule
    }


# ============================================================
# EMAIL OTP SENDER (GMAIL SMTP)
# ============================================================
def send_fake_otp_to_email(email: str, otp_code: str):
    sender = os.getenv("SENDER_EMAIL")
    password = os.getenv("SENDER_APP_PASSWORD")

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = email
    msg["Subject"] = "Your OTP Verification Code"

    body = f"Your OTP is: {otp_code}\nDo not share this with anyone."
    msg.attach(MIMEText(body, "plain"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, email, msg.as_string())
        server.quit()
        print(f"OTP email sent to {email}")
        return True
    except Exception as e:
        print("Email send error:", e)
        return False


# ============================================================
# SOFT SANCTION (FOIR / EMI-BASED)
# ============================================================
def compute_soft_sanction(income, expense, employment_type, dob, roi=8.5):
    import datetime as _dt

    year = int(dob.split("-")[0])
    current_year = _dt.datetime.now().year
    age = current_year - year

    max_tenure = min(60 - age, 30)
    if max_tenure < 1:
        return 0

    nmi = income - expense
    if nmi <= 0:
        return 0

    foir_factor = 0.50 if employment_type.lower() == "salaried" else 0.40
    eligible_emi = nmi * foir_factor

    r = roi / 100 / 12
    n = max_tenure * 12
    pow_val = (1 + r) ** n

    loan_amt = eligible_emi * (pow_val - 1) / (r * pow_val)
    return round(loan_amt, 2)
