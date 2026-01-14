import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import google.generativeai as genai
import json
from datetime import datetime
import pandas as pd

# --- CONFIGURATION ---
st.set_page_config(page_title="Gym AI", page_icon="💪", layout="centered")
st.title("💪 AI Workout Tracker")

# 1. Setup AI
try:
    genai.configure(api_key=st.secrets["general"]["gemini_api_key"])
except Exception as e:
    st.error(f"API Key Error: {e}")

# 2. Database Connection (Cached)
@st.cache_resource
def get_db_connection():
    key_content = st.secrets["gcp_service_account"]["json_key"]
    creds_dict = json.loads(key_content, strict=False)
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

# 3. AI Parsing Logic
def parse_workout(text):
    MODEL_NAME = 'models/gemini-2.5-flash'
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        prompt = f"""
        Extract workout data from: "{text}".
        Return ONLY a JSON list with keys: "exercise" (Standardize name, e.g. 'Bench Press'), "weight" (int), "reps" (int), "notes".
        If weight is missing, use 0.
        """
        response = model.generate_content(prompt)
        cleaned_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(cleaned_text)
    except Exception as e:
        return None

# --- UI LAYOUT: TABS ---
tab1, tab2 = st.tabs(["📝 Log Workout", "📈 Check Progress"])

# ==========================================
# TAB 1: LOGGING (The Input)
# ==========================================
with tab1:
    st.header("New Entry")
    with st.form("workout_form"):
        user_input = st.text_area("How was your workout?", height=120, 
                                  placeholder="e.g., Squats 80kg for 5 reps, 3 sets.")
        submitted = st.form_submit_button("Log It")

    if submitted and user_input:
        with st.spinner("AI is analyzing..."):
            workout_data = parse_workout(user_input)
            
            if workout_data:
                try:
                    client = get_db_connection()
                    sh = client.open("My Workout DB")
                    ex_sheet = sh.worksheet("Exercises")
                    
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    # We save the DATE separately for easier charting
                    date_only = datetime.now().strftime("%Y-%m-%d")
                    
                    rows = []
                    for item in workout_data:
                        rows.append([
                            date_only, # Column A: Date
                            item.get('exercise', 'Unknown').title(), # Column B: Exercise (Title Case)
                            item.get('weight', 0), # Column C: Weight
                            item.get('reps', 0),   # Column D: Reps
                            item.get('notes', '')  # Column E: Notes
                        ])
                    
                    ex_sheet.append_rows(rows)
                    st.success(f"✅ Logged {len(rows)} sets!")
                    
                    # Clear cache so the charts update immediately
                    st.cache_data.clear()
                    
                except Exception as e:
                    st.error(f"Save Error: {e}")
            else:
                st.error("AI couldn't understand that. Try being more specific.")

# ==========================================
# TAB 2: ANALYTICS (The Charts)
# ==========================================
with tab2:
    st.header("Growth Tracker")
    
    # Function to fetch data (Cached so it's fast)
    @st.cache_data(ttl=60) # Refreshes every 60 seconds automatically
    def load_data():
        try:
            client = get_db_connection()
            sheet = client.open("My Workout DB").worksheet("Exercises")
            data = sheet.get_all_records()
            return pd.DataFrame(data)
        except:
            return pd.DataFrame()

    df = load_data()

    if not df.empty:
        # 1. Exercise Selector
        # Get unique exercises, sort them
        all_exercises = sorted(df['Exercise'].unique().tolist())
        selected_exercise = st.selectbox("Select Exercise to Analyze:", all_exercises)
        
        # 2. Filter Data
        # We look only at the exercise you selected
        subset = df[df['Exercise'] == selected_exercise].copy()
        
        # Convert columns to numbers just in case
        subset['Weight'] = pd.to_numeric(subset['Weight'], errors='coerce')
        subset['Reps'] = pd.to_numeric(subset['Reps'], errors='coerce')
        
        # 3. Calculate "Max Weight" per Date
        # This shows your strength gains
        progress_df = subset.groupby('Date')['Weight'].max().reset_index()
        
        # 4. Show Chart
        st.subheader(f"Max Weight: {selected_exercise}")
        st.line_chart(progress_df.set_index('Date'))
        
        # 5. Stats
        best_lift = progress_df['Weight'].max()
        st.metric("All Time Best (1RM Estimate)", f"{best_lift} kg")
        
        # 6. Recent History Table
        with st.expander(f"See History for {selected_exercise}"):
            st.dataframe(subset[['Date', 'Weight', 'Reps', 'Notes']].tail(10))
            
    else:
        st.info("No data yet. Go to the 'Log' tab and enter your first workout!")