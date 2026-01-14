import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import google.generativeai as genai
import json
from datetime import datetime
import pandas as pd

# --- CONFIGURATION ---
st.set_page_config(page_title="Gym AI", page_icon="💪")
st.title("💪 AI Workout Logger")

# 1. Setup AI
try:
    genai.configure(api_key=st.secrets["general"]["gemini_api_key"])
except Exception as e:
    st.error(f"API Key Error: {e}")

# --- DATABASE CONNECTION (OPTIMIZED) ---
# This decorator keeps the connection open so it doesn't reload every time
@st.cache_resource
def get_db_connection():
    key_content = st.secrets["gcp_service_account"]["json_key"]
    creds_dict = json.loads(key_content, strict=False)
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

# --- THE BRAIN ---
def parse_workout(text):
    MODEL_NAME = 'models/gemini-2.5-flash'
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        prompt = f"""
        Extract workout data from: "{text}".
        Return ONLY a JSON list with keys: "exercise", "weight" (int), "reps" (int), "notes".
        If weight is missing, use 0.
        """
        response = model.generate_content(prompt)
        cleaned_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(cleaned_text)
    except Exception as e:
        st.error(f"AI Error: {e}")
        return None

# --- MAIN FORM ---
with st.form("workout_form"):
    user_input = st.text_area("Tell me what you did:", height=100, placeholder="e.g., Bench Press 60kg for 10 reps...")
    submitted = st.form_submit_button("Log Workout")

if submitted and user_input:
    # 1. AI Processing
    with st.spinner("AI is thinking..."):
        workout_data = parse_workout(user_input)

    # 2. Saving to DB
    if workout_data:
        with st.spinner("Saving to Google Sheets..."):
            try:
                client = get_db_connection()
                sh = client.open("My Workout DB")
                ex_sheet = sh.worksheet("Exercises")
                
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                rows = []
                for item in workout_data:
                    rows.append([
                        timestamp,
                        item.get('exercise', 'Unknown'),
                        item.get('weight', 0),
                        item.get('reps', 0),
                        item.get('notes', '')
                    ])
                
                ex_sheet.append_rows(rows)
                st.success(f"✅ Saved {len(rows)} sets!")
                
            except Exception as e:
                st.error(f"Database Error: {e}")
                # Clear cache if connection dropped
                st.cache_resource.clear()
    else:
        st.error("Could not parse data.")

# --- ANALYTICS PREVIEW (The Next Step) ---
st.divider()
st.subheader("📊 Quick Stats")
if st.button("Refresh Charts"):
    client = get_db_connection()
    sheet = client.open("My Workout DB").worksheet("Exercises")
    data = sheet.get_all_records()
    if data:
        df = pd.DataFrame(data)
        # Quick Chart: Total Reps per Exercise
        st.bar_chart(df.groupby("Exercise")["Reps"].sum())