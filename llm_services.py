# llm_services.py
import json
import re
import utils
from typing import Dict, Any, List

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

import config
import prompts
from google.auth import default
credentials, project = default()

# --- LLM Initialization ---
def get_llm() -> ChatGoogleGenerativeAI:
    """Initializes and returns the Gemini LLM instance."""
    return ChatGoogleGenerativeAI(
        model=config.MODEL_NAME,
        credentials=credentials,   # ✅ FIXED
        temperature=config.LLM_TEMPERATURE
    )

llm = get_llm()

# --- Helper to parse dirty JSON from LLM ---
def parse_llm_json_output(llm_output: str) -> Dict[str, Any]:
    """Tries to find and parse a JSON object from the LLM's string output."""
    try:
        # Find the first '{' and last '}'
        json_match = re.search(r'\{.*\}', llm_output, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            return json.loads(json_str)
        else:
            print(f"Warning: No JSON object found in LLM output: {llm_output}")
            return {"error": "No JSON object found"}
    except json.JSONDecodeError as e:
        print(f"Error: Could not decode JSON from LLM: {e}\nOutput: {llm_output}")
        return {"error": "JSONDecodeError", "message": str(e)}

# --- 1. Intent Detection Service (Requirement 6) ---
def detect_intent_with_llm(query: str, history: List[Dict[str, str]]) -> Dict[str, Any]:
    """Detects intent using the LLM based on query and history."""
    history_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history])
    
    prompt_template = ChatPromptTemplate.from_template(prompts.INTENT_PROMPT)
    chain = prompt_template | llm | StrOutputParser()
    
    response = chain.invoke({
        "history": history_str,
        "query": query
    })
    
    return parse_llm_json_output(response)

# --- 2. EMI Schedule Service (Requirement 5) ---
def get_emi_schedule_from_gemini(principal: float, roi: float, tenure: int) -> Dict[str, Any]:
    """
    Compute EMI schedule locally (fast) using utils.compute_emi_schedule.
    Kept the original function name so agent.py doesn't need changes.
    """
    try:
        emi_result = utils.compute_emi_schedule(principal, roi, tenure)
        if emi_result.get("error"):
            return {"error": "Failed to compute EMI", "details": emi_result}
        return emi_result
    except Exception as e:
        return {"error": "Exception during EMI computation", "details": str(e)}

    
    return json_response

# --- 3. Eligibility Check Service (Requirement 7, 13) ---
def check_eligibility_with_gemini(data: Dict[str, Any]) -> Dict[str, Any]:
    """Calls Gemini to perform a soft sanction check."""
    prompt_template = ChatPromptTemplate.from_template(prompts.ELIGIBILITY_PROMPT)
    chain = prompt_template | llm | StrOutputParser()
    
    response = chain.invoke(data)
    json_response = parse_llm_json_output(response)
    
    if "error" in json_response:
        # Fallback or error handling
        return {"error": "Failed to check eligibility", "details": json_response}

    return json_response

# --- 4. RAG Response Service ---
def get_rag_response(query: str, context: str) -> str:
    """Generates a RAG response based on query and context."""
    prompt_template = ChatPromptTemplate.from_template(prompts.RAG_PROMPT)
    chain = prompt_template | llm | StrOutputParser()
    
    response = chain.invoke({
        "context": context,
        "query": query
    })
    
    return response

def classify_emi_input(query: str, waiting_for: str) -> str:
    """
    Classifies EMI input:
    - 'value' → user is giving principal/tenure/ROI
    - 'other' → user is asking a general question
    """

    prompt = f"""
You are an EMI input classifier.

The user is expected to provide: {waiting_for}

Decide:
- If the user message is ONLY giving the required value (like "50 lakhs", "20", "8.5%", "5000000"), respond ONLY with: value
- If the user message is asking any other question (even if it contains a number), respond ONLY with: other

User message: "{query}"

Output ONLY one word: value or other
"""

    # 🔥 Use SAME pattern as your other LLM calls
    chain = (
        ChatPromptTemplate.from_template("{prompt}")
        | llm
        | StrOutputParser()
    )

    result = chain.invoke({"prompt": prompt}).strip().lower()

    return "value" if "value" in result else "other"



def classify_eligibility_input(query: str, field: str) -> str:
    """
    Classifies if the user message is:
    - 'value'  → user is giving the requested number
    - 'other'  → user is asking a question or talking about something else
    """

    prompt = f"""
You are an input classifier for home loan eligibility.

The expected field is: {field}

Decide:
- If the user message is ONLY giving the required value 
  (e.g., "15000", "0", "no expenses"), respond ONLY with: value
- If the user message is a question or unrelated sentence,
  EVEN IF it contains a number, respond ONLY with: other

User message: "{query}"

Output ONLY one word: value or other
"""

    chain = (
        ChatPromptTemplate.from_template("{prompt}")
        | llm
        | StrOutputParser()
    )

    result = chain.invoke({"prompt": prompt}).strip().lower()
    return "value" if "value" in result else "other"
