import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
from datetime import datetime

# --- SETUP DATABASE CONNECTION ---
def get_db_connection():
    # We load the secret key we saved in Streamlit Cloud
    key_content = st.secrets["gcp_service_account"]["json_key"]
    creds_dict = json.loads(key_content)
    
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    # Connect to your specific sheet name
    sheet = client.open("My Workout DB").worksheet("Raw Logs")
    return sheet

st.title("🏋️ Gym DB Connector")

# --- TEST THE CONNECTION ---
if st.button("Save Test Entry"):
    try:
        sheet = get_db_connection()
        # Add a row: [Date, Message, Status]
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([current_time, "Connection Test", "Success!"])
        st.success(f"Saved to Google Sheets at {current_time}!")
    except Exception as e:
        st.error(f"Error: {e}")