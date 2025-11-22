import os
from google.cloud import bigquery
from dotenv import load_dotenv

# --- LOAD ENV VARIABLES ---
load_dotenv()
GCP_PROJECT_ID = os.getenv("BIGQUERY_PROJECT_ID") # august-edge-475606-s9
BQ_DATASET_ID = os.getenv("BIGQUERY_DATASET") # rag_chatbot_conversation

CONVERSATION_TABLE_ID = f"{GCP_PROJECT_ID}.{BQ_DATASET_ID}.tbl_conversation"
EXTRACTED_TABLE_ID = f"{GCP_PROJECT_ID}.{BQ_DATASET_ID}.tbl_extracted_data"

# --- SCHEMAS AS PER YOUR SCREENSHOT ---
SCHEMA_CONVERSATION = [
    bigquery.SchemaField("session_id", "INT64", mode="REQUIRED"),
    bigquery.SchemaField("conversation", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("time_stamp", "DATETIME", mode="NULLABLE")
]

SCHEMA_EXTRACTED = [
    bigquery.SchemaField("session_id", "INT64", mode="REQUIRED"),
    bigquery.SchemaField("customer_name", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("email", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("extracted_data", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("phone_number", "STRING", mode="NULLABLE")
]

def reset_table(table_id, schema):
    client = bigquery.Client(project=GCP_PROJECT_ID)

    print(f"\n🔄 Deleting table if exists: {table_id}")
    try:
        client.delete_table(table_id, not_found_ok=True)
        print("✅ Table deleted")
    except Exception as e:
        print(f"⚠️ Delete error: {e}")

    print(f"🛠 Creating table: {table_id}")
    try:
        table = bigquery.Table(table_id, schema=schema)
        client.create_table(table)
        print("✅ Table created")
    except Exception as e:
        print(f"⚠️ Create error: {e}")


if __name__ == "__main__":
    print("\n############################")
    print(" RESETTING BIGQUERY TABLES ")
    print("############################\n")

    reset_table(CONVERSATION_TABLE_ID, SCHEMA_CONVERSATION)
    reset_table(EXTRACTED_TABLE_ID, SCHEMA_EXTRACTED)
