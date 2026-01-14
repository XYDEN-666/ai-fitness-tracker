import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import google.generativeai as genai
import json
from datetime import datetime
import pandas as pd

# --- CONFIGURATION ---
# 1. Setup AI
genai.configure(api_key=st.secrets["general"]["gemini_api_key"])
model = genai.GenerativeModel('gemini-pro')

# 2. Setup Database
def get_db_connection():
    key_content = st.secrets["gcp_service_account"]["json_key"]
    creds_dict = json.loads(key_content, strict=False)
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

# --- THE BRAIN (AI LOGIC) ---
def parse_workout(text):
    """Turns natural language into a JSON list of sets"""
    prompt = f"""
    You are a gym data assistant. Convert this workout log into a JSON list.
    User Input: "{text}"
    
    Rules:
    1. Output a LIST of objects. One object per SET.
    2. If user says "3 sets of 10 reps at 50kg", output 3 identical objects.
    3. Keys required: "exercise" (string), "weight" (number, just the value), "reps" (number), "notes" (string).
    4. If weight is not specified, put 0.
    5. Return ONLY raw JSON. No markdown formatting.
    
    Example Output format:
    [
        {{"exercise": "Bench Press", "weight": 60, "reps": 10, "notes": "Easy"}},
        {{"exercise": "Bench Press", "weight": 60, "reps": 10, "notes": "Easy"}}
    ]
    """
    try:
        response = model.generate_content(prompt)
        cleaned_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(cleaned_text)
    except Exception as e:
        st.error(f"AI Error: {e}")
        return None

# --- THE UI (What you see on iPhone) ---
st.set_page_config(page_title="Gym AI", page_icon="💪")
st.title("💪 AI Workout Logger")

# Form for input (prevents reloading while typing)
with st.form("workout_form"):
    user_input = st.text_area("Tell me what you did:", height=150, 
                              placeholder="e.g., Squats 60kg 5x5, then Bench 40kg 3 sets of 10...")
    submitted = st.form_submit_button("Log Workout")

if submitted and user_input:
    with st.spinner("AI is crunching the numbers..."):
        # 1. Parse Data
        workout_data = parse_workout(user_input)
        
        if workout_data:
            # 2. Connect to Sheets
            client = get_db_connection()
            sh = client.open("My Workout DB")
            
            # 3. Save Raw Log (For backup)
            raw_sheet = sh.worksheet("Raw Logs")
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            raw_sheet.append_row([timestamp, user_input, "Processed"])
            
            # 4. Save Structured Data (The Magic)
            ex_sheet = sh.worksheet("Exercises")
            rows_to_add = []
            for set_data in workout_data:
                rows_to_add.append([
                    timestamp, 
                    set_data.get('exercise', 'Unknown'),
                    set_data.get('weight', 0),
                    set_data.get('reps', 0),
                    set_data.get('notes', '')
                ])
            
            # Batch update for speed
            ex_sheet.append_rows(rows_to_add)
            
            st.success(f"✅ Saved {len(rows_to_add)} sets to database!")
            st.table(pd.DataFrame(workout_data)) # Show what was saved
        else:
            st.error("Could not understand input. Try again.")

# --- HISTORY PREVIEW ---
st.write("---")
st.subheader("Recent History")
if st.button("Refresh Data"):
    client = get_db_connection()
    sheet = client.open("My Workout DB").worksheet("Exercises")
    data = sheet.get_all_records()
    if data:
        df = pd.DataFrame(data)
        st.dataframe(df.tail(5)) # Show last 5 rows