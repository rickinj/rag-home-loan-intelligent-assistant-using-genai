# agent.py
from typing import Dict, Any, Tuple, Optional
import re
import datetime
import logging

import config
import llm_services
import rag_processor
import utils
from utils import parse_number_from_string, compute_emi_schedule

# Setup logger
logger = logging.getLogger("agent")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

# ---------------------------
# QUESTION DETECTOR
# ---------------------------
def is_question(text: str) -> bool:
    text = text.lower().strip()
    question_words = ["how", "what", "why", "when", "where", "tell", "give", "explain"]
    if text.endswith("?"):
        return True
    return any(text.startswith(w) for w in question_words)

# ---------------------------
# Public entrypoint
# ---------------------------
def agent_controller(query: str, state: Dict[str, Any], vector_db) -> Tuple[str, Dict[str, Any]]:
    state.setdefault("vector_db", vector_db)
    state.setdefault("chat_history", state.get("chat_history", []))
    q = (query or "").strip()
    state["last_user_query"] = q

    # THANK YOU HANDLER (mark conversation complete)
    thank_you_phrases = {"thank you", "thanks", "ok thank you", "okay thank you", "thankyou", "thx"}
    if q.lower() in thank_you_phrases or any(p in q.lower() for p in thank_you_phrases):
        state["conversation_complete"] = True
        return (
            "You're welcome! 😊\n\nIf you need help with EMI, eligibility, or any home-loan policy, feel free to ask.",
            state
        )

    # Intent detection (LLM)
    try:
        history = state.get("chat_history", [])
        intent_data = llm_services.detect_intent_with_llm(q, history)
        intent = intent_data.get("intent", "ask_rag")
    except Exception as e:
        logger.warning(f"Intent detection failed: {e}. Defaulting to ask_rag.")
        intent = "ask_rag"

    state["intent"] = intent
    state.setdefault("current_flow", "initial")
    current_flow = state["current_flow"]

    # ROUTER
    if current_flow == "initial":
        return _handle_initial(intent, state)
    if current_flow == "collect_emi":
        return handle_emi_flow(q, state)
    if current_flow == "post_emi":
        return _handle_post_emi(intent, state)
    if current_flow == "collect_eligibility":
        return handle_eligibility_flow(q, state)
    if current_flow == "collect_name":
        return collect_name(q, state)
    if current_flow == "collect_phone":
        return collect_phone(q, state)
    if current_flow == "collect_email":
        return collect_email(q, state)
    if current_flow == "collect_otp":
        return collect_otp(q, state)
    if current_flow == "post_flow_info":
        return post_flow_info(q, state)
    if current_flow == "rag":

        # ⭐ Allow restarting EMI from anywhere
        if intent == "start_emi" or any(x in q.lower() for x in ["emi", "calculate emi", "check my emi", "emi calculation"]):
            state["current_flow"] = "collect_emi"
            state["waiting_for"] = "principal"
            return "Sure! Please provide your Principal Loan Amount.", state

        # ⭐ Allow starting Eligibility from anywhere
        if intent == "start_eligibility" or "eligib" in q.lower():
            state["current_flow"] = "collect_eligibility"
            state["waiting_for"] = "income"
            return "Sure! Let's check your eligibility.\n\nPlease provide your Monthly Income.", state

        # Default RAG
        return handle_rag_flow(q, state.get("vector_db")), state

    state = _reset_flows(state)
    return "I'm sorry, I got confused. Let's start over. How can I help?", state


# ---------------------------
# INITIAL HANDLER
# ---------------------------
def _handle_initial(intent: str, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    if intent == "start_emi":
        state["current_flow"] = "collect_emi"
        state["waiting_for"] = "principal"
        _clear_emi_and_eligibility(state)
        return "Great! To calculate your EMI, please provide the **Principal Loan Amount**", state

    if intent == "start_eligibility":
        state["current_flow"] = "collect_eligibility"
        state["waiting_for"] = "income"
        _clear_emi_and_eligibility(state)
        return "Sure! To check eligibility, please provide your **Monthly Income**.", state

    if intent == "ask_rag":
        state["current_flow"] = "rag"
        state["waiting_for"] = None
        return handle_rag_flow("", state.get("vector_db")), state

    if intent == "greeting":
        return "Hello! How can I assist you with your Home Loan today?", state

    return "I'm sorry, I didn't understand that.", state


# ---------------------------
# RAG handler
# ---------------------------
def handle_rag_flow(query: str, vector_db) -> str:
    context = rag_processor.get_retrieved_context(query, vector_db)
    return llm_services.get_rag_response(query, context) + "\n\n**Would you like to calculate your EMI?**"


# ---------------------------
# EMI Flow
# ---------------------------
def handle_emi_flow(query: str, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    waiting = state.get("waiting_for")

    if waiting == "principal":
        classification = safe_classify_emi_input(query, "principal")
        if classification == "value":
            value = parse_number_from_string(query)
            if value and value > 0:
                state["principal"] = value
                state["waiting_for"] = "tenure"
                return "Got it. What is the **Loan Tenure** (in years)?", state
            return "Please provide a valid principal.", state

        ctx = rag_processor.get_retrieved_context(query, state.get("vector_db"))
        ans = llm_services.get_rag_response(query, ctx)
        ans += "\n\nPlease provide the principal amount."
        return ans, state

    if waiting == "tenure":
        classification = safe_classify_emi_input(query, "tenure")
        if classification == "value":
            value = parse_number_from_string(query)
            if value and 1 <= value <= 30:
                state["tenure"] = int(value)
                state["waiting_for"] = "roi"
                return "Great. What is the **Rate of Interest (ROI)**?", state
            return "Please provide a valid tenure between 1–30 years.", state

        ctx = rag_processor.get_retrieved_context(query, state.get("vector_db"))
        ans = llm_services.get_rag_response(query, ctx)
        ans += "\n\nPlease provide the tenure."
        return ans, state

    if waiting == "roi":
        classification = safe_classify_emi_input(query, "interest rate")
        if classification == "value":
            value = parse_number_from_string(query)
            if value and value > 0:
                state["roi"] = float(value)

                emi_result = compute_emi_schedule(
                    principal=state.get("principal"),
                    annual_rate_percent=state.get("roi"),
                    tenure_years=state.get("tenure")
                )

                state["emi_result"] = emi_result
                state["emi_summary"] = {
                    "monthly_emi": emi_result.get("monthly_emi"),
                    "total_interest": emi_result.get("total_interest"),
                    "total_payment": emi_result.get("total_payment"),
                }

                state["emi_done"] = True  # ✔ FOR BIGQUERY SAVE
                state["current_flow"] = "post_emi"
                state["waiting_for"] = None

                state["show_emi_once"] = True

                msg = (
                    "### ✅ EMI Calculation Complete\n"
                    f"**Monthly EMI:** ₹{emi_result.get('monthly_emi')}\n"
                    f"**Total Interest:** ₹{emi_result.get('total_interest')}\n"
                    f"**Total Payment:** ₹{emi_result.get('total_payment')}\n\n"
                    "**Would you like to check your eligibility? (Yes/No)**"
                )
                return msg, state

            return "Please provide a valid interest rate.", state

        ctx = rag_processor.get_retrieved_context(query, state.get("vector_db"))
        ans = llm_services.get_rag_response(query, ctx)
        ans += "\n\nPlease provide ROI."
        return ans, state

    return "Sorry, let's restart the EMI flow.", state


# ---------------------------
# POST EMI
# ---------------------------
def _handle_post_emi(intent: str, state: Dict[str, Any]):
    """
    Handles Yes/No after EMI. 
    If user asks another question (not yes/no),
    answer with RAG but STILL stay inside post_emi flow
    until the user says Yes or No.
    """

    # CASE 1: User asks another RAG question (NOT yes/no)
    if intent not in ["affirmative", "negative"]:
        query = state.get("last_user_query", "")
        rag_answer = handle_rag_flow(query, state.get("vector_db"))

        # Stay inside post_emi
        state["current_flow"] = "post_emi"

        return rag_answer + "\n\nPlease answer Yes or No.", state

    # CASE 2: YES → begin eligibility
    if intent == "affirmative":
        state["current_flow"] = "collect_eligibility"
        state["waiting_for"] = "income"
        return "Great! Please share your *Monthly Income*.", state

    # CASE 3: NO → contact flow
    if intent == "negative":
        state["save_on_emi_no"] = True
        state["current_flow"] = "post_flow_info"
        state["waiting_for"] = "info_decision"
        return "Would you like our representative to contact you? (Yes/No)", state

    return "Please answer Yes or No.", state


# ---------------------------
# ELIGIBILITY FLOW (FULL NAME ADDED)
# ---------------------------
def handle_eligibility_flow(query: str, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    waiting = state.get("waiting_for")

    def rag_with(msg: str):
        ctx = rag_processor.get_retrieved_context(query, state.get("vector_db"))
        return llm_services.get_rag_response(query, ctx) + f"\n\n{msg}", state

    # 1. income
    if waiting == "income":
        if safe_classify_eligibility_input(query, "income") == "value":
            val = parse_number_from_string(query)
            if val and val > 0:
                state["income"] = val
                state["waiting_for"] = "expense"
                return "Thanks. What are your **Monthly Expenses**?", state
        return rag_with("Please provide Monthly Income.")

    # 2. expense
    if waiting == "expense":
        if safe_classify_eligibility_input(query, "expense") == "value":
            val = parse_number_from_string(query)
            if val is not None and val >= 0:
                state["expense"] = val
                state["waiting_for"] = "employment_type"
                return "Got it. Are you **Salaried** or **Self-Employed**?", state
        return rag_with("Please provide Monthly Expenses.")

    # 3. employment
    if waiting == "employment_type":
        q = query.lower()
        if "salaried" in q:
            state["employment_type"] = "Salaried"
        elif "self" in q:
            state["employment_type"] = "Self-Employed"
        else:
            return rag_with("Please specify Salaried or Self-Employed.")
        state["waiting_for"] = "dob"
        return "What is your **Date of Birth**? (YYYY-MM-DD)", state

    # 4. dob
    if waiting == "dob":
        if re.match(r"^\d{4}-\d{2}-\d{2}$", query):
            state["dob"] = query
            state["waiting_for"] = "pin_code"
            return "Thanks. What is your **Pincode**?", state
        return rag_with("Please provide DOB in YYYY-MM-DD format.")

    # 5. Pincode
    if waiting == "pin_code":
        if re.match(r"^\d{6}$", query.strip()):
            state["pin_code"] = query
            state["waiting_for"] = "loan_type"
            return "Is this for a **Fresh Loan** or a **Balance Transfer**?", state
        return rag_with("Please provide a 6-digit pincode.")

    # 6. loan type
    if waiting == "loan_type":
        q = query.lower()
        if "fresh" in q:
            state["loan_type"] = "Fresh"
        elif "balance" in q or "transfer" in q:
            state["loan_type"] = "Balance Transfer"
        else:
            return rag_with("Please specify Fresh Loan or Balance Transfer.")
        state["waiting_for"] = "name"
        return "Great! Before we continue, may I know your **Full Name** (e.g., Rohan Sharma).?", state

    # 7. NAME (NEW ✔)
    if waiting == "name":

        # Asking for name again after phone is already collected
        if state.get("customer_name") and state.get("phone"):
            state["waiting_for"] = "email"
            state["current_flow"] = "collect_email"
            return "Thanks! Now please share your **email address**.", state

        # If user is asking a question → answer via RAG first
        if is_question(query):
            ctx = rag_processor.get_retrieved_context(query, state.get("vector_db"))
            ans = llm_services.get_rag_response(query, ctx)
            ans += "\n\nPlease enter your full name (e.g., Rohan Sharma)."
            return ans, state

        # Validate exact 2-word name
        name_parts = query.strip().split()
        if len(name_parts) == 2:
            state["customer_name"] = query.title()
            state["waiting_for"] = "phone"
            state["current_flow"] = "collect_phone"
            return "Thank you! Please provide your **10-digit mobile number**.", state

        return "Please enter your full name (e.g., Rohan Sharma).", state


    # 8. PHONE
    if waiting == "phone":
        if re.match(r"^\d{10}$", query):
            state["phone"] = query
            state["waiting_for"] = "email"
            state["current_flow_before_email"] = "eligibility_flow"
            return "Thanks! Now your **Email Address**, please.", state
        return rag_with("Please enter a valid 10-digit mobile number.")

    # 9. EMAIL
    if waiting == "email":
        email = query.strip().lower()
        if not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email):
            return rag_with("Please enter a valid email.")
        state["email"] = email
        state["otp_mode"] = "eligibility"

        otp = utils.generate_otp()
        state["generated_otp"] = otp
        utils.send_fake_otp_to_email(email, otp)

        state["current_flow"] = "collect_otp"
        state["waiting_for"] = "otp"
        return (f"OTP sent to **{email}**. Please enter the 6-digit OTP.", state)

    return "Sorry, let's restart eligibility.", state


# ---------------------------
# NAME (for contact flow)
# ---------------------------
def collect_name(query, state):

    # Asking for name again if already collected
    if state.get("customer_name") and state.get("phone"):
        state["current_flow"] = "collect_email"
        state["waiting_for"] = "email"
        return "Thanks! Now please share your *email address*.", state

    # If user asks a RAG question → answer first
    if is_question(query):
        ctx = rag_processor.get_retrieved_context(query, state.get("vector_db"))
        ans = llm_services.get_rag_response(query, ctx)
        ans += "\n\nPlease enter your full name (e.g., Neha Sharma)."
        return ans, state

    # Exact 2-word full name required
    name_parts = query.strip().split()
    if len(name_parts) == 2:
        state["customer_name"] = query.title()
        state["current_flow"] = "collect_phone"
        state["waiting_for"] = "phone"
        return "Thank you! Please provide your 10-digit mobile number.", state

    return "Please enter your full name (e.g., Neha Sharma).", state


# ---------------------------
# PHONE (generic)
# ---------------------------
def collect_phone(query: str, state: Dict[str, Any]):
    if re.match(r"^\d{10}$", query):
        state["phone"] = query
        if state.get("current_flow_before_email") is None:
            state["current_flow_before_email"] = "contact_flow"
        state["current_flow"] = "collect_email"
        state["waiting_for"] = "email"
        return "Thanks! Now please share your *email address*.", state

    return "Invalid phone number. Please enter a 10-digit mobile number.", state


# ---------------------------
# EMAIL (generic)
# ---------------------------
def collect_email(query: str, state: Dict[str, Any]):
    email = query.strip()
    if not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email):
        return "Please provide a valid email address.", state

    state["email"] = email

    if state.get("current_flow_before_email") == "eligibility_flow":
        state["otp_mode"] = "eligibility"
    else:
        state["otp_mode"] = "contact"

    otp = utils.generate_otp()
    state["generated_otp"] = otp
    utils.send_fake_otp_to_email(email, otp)

    state["current_flow"] = "collect_otp"
    state["waiting_for"] = "otp"

    return (f"OTP has been sent to {email}. Please enter the OTP.", state)


# ---------------------------
# OTP verification
# ---------------------------
def collect_otp(query: str, state: Dict[str, Any]):
    otp_mode = state.get("otp_mode")
    generated = state.get("generated_otp")

    if not generated:
        state["current_flow"] = "collect_email"
        state["waiting_for"] = "email"
        return "OTP missing. Let's restart email verification.", state

    if utils.verify_otp(query.strip(), generated):
        if otp_mode == "eligibility":
            loan_amount = utils.compute_soft_sanction(
                state.get("income"),
                state.get("expense"),
                state.get("employment_type"),
                state.get("dob")
            )

            if loan_amount >= 500000:
                result = {
                    "eligible": True,
                    "sanction_amount": loan_amount,
                    "reason": "Based on FOIR and EMI capacity."
                }
            else:
                result = {
                    "eligible": False,
                    "sanction_amount": loan_amount,
                    "reason": "Income and FOIR allow only a low sanction amount."
                }

            state["eligibility_result"] = result
            state["eligibility_done"] = True  # ✔ FOR BIGQUERY SAVE

            if result["eligible"]:
                amt = utils.format_indian_style(result["sanction_amount"])
                msg = f"🎉 **Eligibility Verified!**\nSoft sanction: **₹{amt}**.\n\nWould you like our representative to contact you?"
            else:
                msg = (
                    f"Eligibility verified, but sanction amount is low.\n"
                    f"Reason: {result['reason']}\n\nWould you like a representative to contact you?"
                )

            state["current_flow"] = "post_flow_info"
            state["waiting_for"] = "info_decision"

            state.pop("otp_mode", None)
            state.pop("generated_otp", None)
            state.pop("current_flow_before_email", None)

            return msg, state

        # CONTACT MODE
        state["current_flow"] = "rag"
        state["waiting_for"] = None

        state.pop("otp_mode", None)
        state.pop("generated_otp", None)
        state.pop("current_flow_before_email", None)

        return ("Verification successful! Our representative will contact you shortly.", state)

    return "Incorrect OTP. Please try again.", state


# ---------------------------
# Post Flow Info
# ---------------------------
def post_flow_info(query: str, state: Dict[str, Any]):
    try:
        intent_data = llm_services.detect_intent_with_llm(query, state.get("chat_history", []))
        intent = intent_data.get("intent", None)
    except Exception:
        intent = None

    if intent == "affirmative" or query.lower() in {"yes", "y", "sure"}:
        state["current_flow"] = "collect_name"
        state["waiting_for"] = "name"
        return "Great! May I know your **Full Name** (e.g., Rohan Sharma)?", state

    if intent == "negative" or query.lower() in {"no", "n"}:
        state["current_flow"] = "rag"
        state["waiting_for"] = None
        return "Alright. Anything else I can help you with?", state

    return "Please reply Yes or No.", state


# ---------------------------
# CLEAR & RESET HELPERS
# ---------------------------
def _clear_emi_and_eligibility(state: Dict[str, Any]):
    keys = [
        "principal", "tenure", "roi",
        "income", "expense", "employment_type", "dob", "pin_code", "loan_type",
        "customer_name",
        "phone", "email",
        "generated_otp", "otp_mode", "current_flow_before_email",
        "emi_result", "emi_summary", "eligibility_result"
    ]
    for k in keys:
        state.pop(k, None)


def _reset_flows(state: Dict[str, Any]) -> Dict[str, Any]:
    preserved = {
        "session_id": state.get("session_id"),
        "chat_history": state.get("chat_history", []),
        "vector_db": state.get("vector_db")
    }
    state.clear()
    state.update({
        "current_flow": "initial",
        "waiting_for": None,
        "product": "home_loan_queries",
        "intent": "greeting",
    })
    state.update(preserved)
    return state


# ---------------------------
# SAFE CLASSIFIERS
# ---------------------------
def safe_classify_emi_input(query: str, waiting_for: str) -> str:
    try:
        return llm_services.classify_emi_input(query, waiting_for)
    except Exception:
        if re.search(r"^\s*[\d\.,]+\s*(lakh|lakhs|lac|lacs|cr|crore|k|years|yrs|%)?\s*$", query.lower()):
            return "value"
        return "other"


def safe_classify_eligibility_input(query: str, field: str) -> str:
    try:
        return llm_services.classify_eligibility_input(query, field)
    except Exception:
        if (
            re.search(r"^\s*[\d\.,]+\s*(lakh|lakhs|lac|lacs|cr|crore|k)?\s*$", query.lower())
            or query.strip() in {"0", "none", "no expenses"}
        ):
            return "value"
        return "other"
