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

# --- DIAGNOSTIC TOOL (Use this if it fails) ---
with st.expander("🛠️ Debugging Tools (Click if error)"):
    st.write("If the app crashes, click below to see valid model names:")
    if st.button("List My Available Models"):
        try:
            st.write("Asking Google...")
            available_models = []
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    available_models.append(m.name)
                    st.write(f"- {m.name}")
            if not available_models:
                st.error("No models found! Check your API Key.")
        except Exception as e:
            st.error(f"Error listing models: {e}")

# --- DATABASE CONNECTION ---
def get_db_connection():
    key_content = st.secrets["gcp_service_account"]["json_key"]
    creds_dict = json.loads(key_content, strict=False)
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

# --- THE BRAIN ---
def parse_workout(text):
    # We use a Try/Except block to automatically find a working model
    working_model = None
    
    # LIST OF MODELS TO TRY (In order of preference)
    model_candidates = [
        'gemini-1.5-flash',
        'models/gemini-1.5-flash',
        'gemini-pro',
        'models/gemini-pro',
        'gemini-1.5-flash-latest'
    ]

    response = None
    last_error = ""

    for model_name in model_candidates:
        try:
            model = genai.GenerativeModel(model_name)
            prompt = f"""
            Extract workout data from: "{text}".
            Return ONLY a JSON list with keys: "exercise", "weight" (int), "reps" (int), "notes".
            If weight is missing, use 0.
            """
            response = model.generate_content(prompt)
            working_model = model_name # It worked!
            break # Stop trying other models
        except Exception as e:
            last_error = str(e)
            continue # Try the next model

    if response:
        try:
            cleaned_text = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned_text), working_model
        except:
            return None, "JSON Error"
    else:
        st.error(f"All models failed. Last error: {last_error}")
        return None, None

# --- MAIN FORM ---
with st.form("workout_form"):
    user_input = st.text_area("Tell me what you did:", height=100)
    submitted = st.form_submit_button("Log Workout")

if submitted and user_input:
    with st.spinner("AI is processing..."):
        workout_data, model_used = parse_workout(user_input)
        
        if workout_data:
            st.success(f"Success! (Used model: {model_used})")
            
            # Save to Sheets
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
            st.table(pd.DataFrame(workout_data))
        else:
            st.error("Could not parse data.")