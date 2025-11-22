# app.py
import streamlit as st
import pandas as pd
import json

import config
import utils
import rag_processor
import agent 

# ------------------------------------------------------
# PAGE CONFIGURATION
# ------------------------------------------------------
st.set_page_config(
    page_title="RBL Bank Chatbot",
    page_icon="🏦",
    layout="centered"
)

st.title("🏦 RBL Bank Home Loan Assistant")


# ------------------------------------------------------
# LOAD VECTOR DB
# ------------------------------------------------------
try:
    vector_db = rag_processor.load_rag_vector_db()
    if vector_db is None:
        st.error("Failed to load RAG knowledge base. RAG queries will not work.")
except Exception as e:
    st.error(f"Critical error loading RAG DB: {e}")
    vector_db = None


# ------------------------------------------------------
# SESSION INITIALIZATION
# ------------------------------------------------------
if "session_id" not in st.session_state:
    st.session_state.session_id = utils.get_session_id()

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "app_state" not in st.session_state:
    st.session_state.app_state = {
        "current_flow": "initial",
        "waiting_for": None,
        "product": "home_loan_queries",
        "intent": "greeting",
        "principal": None,
        "tenure": None,
        "roi": None,
        "income": None,
        "expense": None,
        "employment_type": None,
        "dob": None,
        "pin_code": None,
        "loan_type": None,
        "customer_name": None,
        "phone": None,
        "email": None,
        "generated_otp": None,
        "emi_result": None,
        "eligibility_result": None,
        "emi_schedule": None,
        "emi_done": None,
        "eligibility_done": None,
        "conversation_complete": None,
        "chat_history": [],
        "vector_db": vector_db
    }


# ------------------------------------------------------
# WELCOME MESSAGE
# ------------------------------------------------------
if not st.session_state.chat_history:
    welcome_msg = (
        "Welcome to RBL Bank Home Loan Assistant! 🏦\n\n"
        "How can I help you today?\n"
        "1. **Calculate EMI**\n"
        "2. **Check Loan Eligibility**\n"
        "3. **Ask a policy question**"
    )
    st.session_state.chat_history.append({"role": "assistant", "content": welcome_msg})


# ------------------------------------------------------
# DISPLAY CHAT HISTORY
# ------------------------------------------------------
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

        # Show EMI schedule only when attached
        if msg.get("display_emi"):
            df = pd.DataFrame(msg["display_emi"]["schedule"])
            with st.expander(f"📅 EMI Schedule ({len(df)} months)"):
                st.dataframe(df)


# ------------------------------------------------------
# USER INPUT
# ------------------------------------------------------
user_input = st.chat_input("Ask about EMI, eligibility, or policies...")

if user_input:

    # Save user msg
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.chat_message("user"):
        st.markdown(user_input)

    # Sync state
    st.session_state.app_state["chat_history"] = st.session_state.chat_history
    st.session_state.app_state["vector_db"] = vector_db

    # AGENT CALL
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                bot_response, updated_state = agent.agent_controller(
                    user_input,
                    st.session_state.app_state,
                    vector_db
                )

                st.session_state.app_state = updated_state

                response_entry = {
                    "role": "assistant",
                    "content": bot_response,
                }

                # Attach EMI schedule if available
                if (
                    updated_state.get("emi_result")
                    and updated_state.get("current_flow") == "post_emi"
                    and updated_state.get("show_emi_once", True)
                ):
                    response_entry["display_emi"] = updated_state["emi_result"]
                    updated_state["show_emi_once"] = False   # <-- STOP FUTURE AUTO-DISPLAYS

                st.markdown(bot_response)

                # Show EMI schedule in UI
                if response_entry.get("display_emi"):
                    df = pd.DataFrame(response_entry["display_emi"]["schedule"])
                    with st.expander(f"📅 EMI Schedule ({len(df)} months)"):
                        st.dataframe(df)

                st.session_state.chat_history.append(response_entry)

            except Exception as e:
                st.error(f"Error: {e}")
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": f"Error: {e}"
                })

    # ------------------------------------------------------
    # SAVE TO BIGQUERY
    # ------------------------------------------------------
    try:
        utils.save_to_bigquery(
            st.session_state.session_id,
            st.session_state.chat_history,
            st.session_state.app_state
        )
    except Exception as e:
        st.error(f"BigQuery save failed: {e}")

