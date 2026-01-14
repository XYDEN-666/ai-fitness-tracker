import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import google.generativeai as genai
import json
from datetime import datetime
import pandas as pd

# --- CONFIGURATION ---
st.set_page_config(page_title="Gym AI", page_icon="🔥", layout="centered")

# --- CUSTOM CSS (Red & Black Theme) ---
st.markdown("""
    <style>
    .stApp {background-color: #0E1117;}
    .stTabs [data-baseweb="tab-list"] {gap: 8px;}
    .stTabs [data-baseweb="tab"] {
        height: 50px; background-color: #1E1E1E; border-radius: 4px 4px 0px 0px;
        padding-top: 10px; padding-bottom: 10px; flex: 1;
    }
    .stTabs [aria-selected="true"] {background-color: #E63946; color: white;}
    .stTextArea textarea {background-color: #262730; color: white; border-radius: 12px; border: 1px solid #444;}
    .stSelectbox > div > div {background-color: #262730; color: white;}
    .stButton > button {
        width: 100%; border-radius: 12px; height: 3em;
        background-color: #E63946; color: white; font-weight: bold; border: none;
    }
    .stButton > button:hover {background-color: #FF4B4B; color: white;}
    header, footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- SETUP ---
try:
    genai.configure(api_key=st.secrets["general"]["gemini_api_key"])
except:
    pass

@st.cache_resource
def get_db_connection():
    key_content = st.secrets["gcp_service_account"]["json_key"]
    creds_dict = json.loads(key_content, strict=False)
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

# --- THE SMART BRAIN (UPDATED) ---
# --- THE PRECISION BRAIN (Updated) ---
def parse_workout(text):
    MODEL_NAME = 'models/gemini-2.5-flash'
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        # We give the AI specific naming conventions
        prompt = f"""
        You are a strict Gym Data Manager. Convert this text: "{text}" into JSON.
        
        CRITICAL NAMING RULES:
        1. "exercise": You must distinguish between Equipment (Barbell vs Dumbbell) and Angle (Flat vs Incline vs Decline).
        2. If user says "Bench Press" or "Bench", default to "Flat Barbell Bench Press".
        3. If user says "DB Bench", map to "Flat Dumbbell Press".
        4. If user says "Incline", map to "Incline Barbell Bench Press" unless they say "Dumbbell/DB".
        
        NAMING EXAMPLES:
        - "bench" -> "Flat Barbell Bench Press"
        - "incline bench" -> "Incline Barbell Bench Press"
        - "incline db press" -> "Incline Dumbbell Press"
        - "decline bench" -> "Decline Barbell Bench Press"
        - "shoulder press" -> "Overhead Barbell Press"
        - "db shoulder press" -> "Seated Dumbbell Shoulder Press"
        
        OTHER RULES:
        - "muscle_group": MUST be one of: [Chest, Back, Legs, Shoulders, Biceps, Triceps, Abs, Cardio].
        - "weight" (int), "reps" (int), "notes" (string).
        
        Example JSON Output:
        [
            {{"exercise": "Incline Dumbbell Press", "muscle_group": "Chest", "weight": 30, "reps": 10, "notes": "Good stretch"}},
            {{"exercise": "Flat Barbell Bench Press", "muscle_group": "Chest", "weight": 80, "reps": 5, "notes": "Heavy"}}
        ]
        """
        response = model.generate_content(prompt)
        cleaned_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(cleaned_text)
    except:
        return None

# --- UI HEADER ---
st.markdown("<h1 style='text-align: center; color: #E63946;'>🔥 XYDEN GYM</h1>", unsafe_allow_html=True)

# --- TABS ---
tab1, tab2 = st.tabs(["📝 LOG", "📈 STATS"])

# ==========================================
# TAB 1: LOGGING
# ==========================================
with tab1:
    st.markdown("###")
    with st.form("workout_form"):
        st.caption("Auto-Detects Muscle Group & Fixes Names")
        user_input = st.text_area("Input", height=100, label_visibility="collapsed",
                                  placeholder="e.g. Bench 60kg 10 reps, then Squats...")
        submitted = st.form_submit_button("LOG SESSION")

    if submitted and user_input:
        with st.spinner("AI is categorizing..."):
            workout_data = parse_workout(user_input)
            if workout_data:
                try:
                    client = get_db_connection()
                    sh = client.open("My Workout DB")
                    ex_sheet = sh.worksheet("Exercises")
                    date_only = datetime.now().strftime("%Y-%m-%d")
                    
                    rows = []
                    for item in workout_data:
                        rows.append([
                            date_only, 
                            item.get('exercise', 'Unknown').title(),
                            item.get('weight', 0),
                            item.get('reps', 0),
                            item.get('notes', ''),
                            item.get('muscle_group', 'Other') # New Column F
                        ])
                    
                    ex_sheet.append_rows(rows)
                    st.cache_data.clear()
                    
                    st.success(f"🔥 Added {len(rows)} sets!")
                    
                    # Smart Preview Card
                    with st.container():
                        for item in workout_data:
                            # Color code the groups
                            group_color = "#E63946" # Default Red
                            if item['muscle_group'] == 'Legs': group_color = "#457b9d"
                            if item['muscle_group'] == 'Back': group_color = "#2a9d8f"
                            
                            st.markdown(f"""
                            <div style="background-color: #262730; padding: 10px; border-radius: 10px; margin-bottom: 5px; border-left: 5px solid {group_color};">
                                <span style="font-size: 0.8em; color: {group_color}; text-transform: uppercase; letter-spacing: 1px;">{item['muscle_group']}</span><br>
                                <strong style="color:white; font-size: 1.1em;">{item['exercise']}</strong><br>
                                <span style="color:#aaa">{item['weight']}kg x {item['reps']}</span>
                            </div>
                            """, unsafe_allow_html=True)

                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.error("AI couldn't process that.")

# ==========================================
# TAB 2: SMART ANALYTICS
# ==========================================
with tab2:
    st.markdown("###")
    
    @st.cache_data(ttl=60)
    def load_data():
        try:
            client = get_db_connection()
            sheet = client.open("My Workout DB").worksheet("Exercises")
            data = sheet.get_all_records()
            df = pd.DataFrame(data)
            
            # CLEAN UP DATA FOR "SMART" VIEW
            # 1. Force Title Case (fixes "bench" vs "Bench")
            df['Exercise'] = df['Exercise'].astype(str).str.title().str.strip()
            
            # 2. Handle missing muscle groups in old data
            if 'Muscle Group' not in df.columns:
                df['Muscle Group'] = 'Uncategorized'
            else:
                df['Muscle Group'] = df['Muscle Group'].replace('', 'Uncategorized')
                
            return df
        except:
            return pd.DataFrame()

    df = load_data()

    if not df.empty:
        # STEP 1: SELECT MUSCLE GROUP
        # Get unique groups, ensure your main ones are at top
        priority_groups = ['Chest', 'Back', 'Legs', 'Shoulders', 'Biceps', 'Triceps', 'Abs']
        available_groups = df['Muscle Group'].unique().tolist()
        # Sort so priority groups come first
        sorted_groups = [g for g in priority_groups if g in available_groups] + [g for g in available_groups if g not in priority_groups]
        
        selected_group = st.selectbox("1. Select Muscle Group", sorted_groups)
        
        # STEP 2: FILTER EXERCISES
        # Only show exercises that belong to the selected group
        subset_group = df[df['Muscle Group'] == selected_group]
        available_exercises = sorted(subset_group['Exercise'].unique().tolist())
        
        if available_exercises:
            selected_exercise = st.selectbox("2. Select Exercise", available_exercises)
            
            # STEP 3: SHOW CHART
            exercise_data = subset_group[subset_group['Exercise'] == selected_exercise].copy()
            exercise_data['Weight'] = pd.to_numeric(exercise_data['Weight'], errors='coerce')
            
            # Find max weight per day
            progress = exercise_data.groupby('Date')['Weight'].max().reset_index()
            
            st.markdown(f"<h3 style='color:#E63946'>{selected_exercise} Progress</h3>", unsafe_allow_html=True)
            st.line_chart(progress.set_index('Date'), color="#E63946")
            
            # Stats
            max_lift = progress['Weight'].max()
            st.info(f"🏆 Personal Record: **{max_lift} kg**")
        else:
            st.warning(f"No exercises found for {selected_group} yet.")
            
    else:
        st.info("Log your first workout to see stats!")