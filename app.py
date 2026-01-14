import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import google.generativeai as genai
import json
from datetime import datetime, timedelta
import pandas as pd

# --- CONFIGURATION ---
st.set_page_config(page_title="Gym AI", page_icon="🔥", layout="centered")

# --- CUSTOM CSS ---
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
    
    /* Progress Bar Color */
    .stProgress > div > div > div > div {
        background-color: #E63946;
    }
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

# --- AI PARSER ---
def parse_workout(text):
    MODEL_NAME = 'models/gemini-2.5-flash'
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        prompt = f"""
        You are a strict Gym Data Manager. Convert this text: "{text}" into JSON.
        
        CRITICAL NAMING RULES:
        1. "exercise": Distinguish Equipment (Barbell/Dumbbell) and Angle (Flat/Incline/Decline).
        2. "muscle_group": MUST be one of: [Chest, Back, Legs, Shoulders, Biceps, Triceps, Abs, Cardio].
        
        EXAMPLES:
        - "bench" -> "Flat Barbell Bench Press"
        - "incline db" -> "Incline Dumbbell Press"
        - "squat" -> "Barbell Back Squat"
        
        Output JSON list with keys: exercise, muscle_group, weight, reps, notes.
        """
        response = model.generate_content(prompt)
        cleaned_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(cleaned_text)
    except:
        return None

# --- AI COACH LOGIC ---
def get_coach_advice(df):
    # Prepare a summary of the last 30 days
    summary = df['Muscle Group'].value_counts().to_string()
    
    MODEL_NAME = 'models/gemini-2.5-flash'
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        prompt = f"""
        I am a bodybuilder. Here is my set volume per muscle group for the last 30 days:
        {summary}
        
        Analyze my training split.
        1. Identify the Most Neglected muscle group.
        2. Identify the Most Overworked muscle group.
        3. Give me 1 specific actionable tip to balance my physique.
        
        Keep it short, brutal, and motivating. Max 3 sentences.
        """
        response = model.generate_content(prompt)
        return response.text
    except:
        return "Coach is on a coffee break. Try again later."

# --- UI HEADER ---
st.markdown("<h1 style='text-align: center; color: #E63946;'>🔥 XYDEN GYM</h1>", unsafe_allow_html=True)

# --- TABS ---
tab1, tab2, tab3 = st.tabs(["📝 LOG", "📈 STATS", "🧠 COACH"])

# ==========================================
# TAB 1: LOGGING
# ==========================================
with tab1:
    st.markdown("###")
    with st.form("workout_form"):
        st.caption("Log your sets:")
        user_input = st.text_area("Input", height=100, label_visibility="collapsed",
                                  placeholder="e.g. Incline DB Press 30kg 10 reps...")
        submitted = st.form_submit_button("LOG SESSION")

    if submitted and user_input:
        with st.spinner("Processing..."):
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
                            item.get('muscle_group', 'Other')
                        ])
                    
                    ex_sheet.append_rows(rows)
                    st.cache_data.clear()
                    
                    st.success(f"🔥 Added {len(rows)} sets!")
                    
                    with st.container():
                        for item in workout_data:
                            group_color = "#E63946"
                            if item['muscle_group'] == 'Legs': group_color = "#457b9d"
                            if item['muscle_group'] == 'Back': group_color = "#2a9d8f"
                            
                            st.markdown(f"""
                            <div style="background-color: #262730; padding: 10px; border-radius: 10px; margin-bottom: 5px; border-left: 5px solid {group_color};">
                                <span style="font-size: 0.8em; color: {group_color}; text-transform: uppercase;">{item['muscle_group']}</span><br>
                                <strong style="color:white;">{item['exercise']}</strong>
                                <span style="color:#aaa; float:right;">{item['weight']}kg x {item['reps']}</span>
                            </div>
                            """, unsafe_allow_html=True)

                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.error("AI Error.")

# ==========================================
# TAB 2: STATS
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
            df['Exercise'] = df['Exercise'].astype(str).str.title().str.strip()
            if 'Muscle Group' not in df.columns: df['Muscle Group'] = 'Uncategorized'
            return df
        except:
            return pd.DataFrame()

    df = load_data()

    if not df.empty:
        # Muscle Group Filter
        groups = sorted(df['Muscle Group'].unique().tolist())
        selected_group = st.selectbox("Filter by Muscle:", groups)
        
        # Exercise Filter
        subset = df[df['Muscle Group'] == selected_group]
        exercises = sorted(subset['Exercise'].unique().tolist())
        
        if exercises:
            selected_ex = st.selectbox("Select Movement:", exercises)
            
            # Chart
            ex_data = subset[subset['Exercise'] == selected_ex].copy()
            ex_data['Weight'] = pd.to_numeric(ex_data['Weight'], errors='coerce')
            progress = ex_data.groupby('Date')['Weight'].max().reset_index()
            
            st.markdown(f"<h3 style='color:#E63946'>{selected_ex}</h3>", unsafe_allow_html=True)
            st.line_chart(progress.set_index('Date'), color="#E63946")
            
            # PR Badge
            max_lift = progress['Weight'].max()
            st.markdown(f"""
            <div style="background-color: #262730; padding: 15px; border-radius: 10px; text-align: center; border: 1px solid #E63946;">
                <span style="color: #aaa;">ALL TIME BEST</span><br>
                <span style="font-size: 2em; font-weight: bold; color: white;">{max_lift} <span style="font-size: 0.5em; color: #E63946;">KG</span></span>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("No exercises found.")

# ==========================================
# TAB 3: AI COACH (WEAKNESS DETECTOR)
# ==========================================
with tab3:
    st.markdown("###")
    st.header("⚖️ Physique Balance")
    
    if not df.empty:
        # 1. VISUAL SPLIT (Bar Chart)
        st.caption("Sets per Muscle Group (All Time)")
        split_counts = df['Muscle Group'].value_counts()
        st.bar_chart(split_counts, color="#E63946")
        
        # 2. AI AUDIT BUTTON
        st.write("---")
        st.caption("Ask the AI where you are lacking:")
        
        if st.button("GENERATE REPORT"):
            with st.spinner("Analyzing your weak points..."):
                advice = get_coach_advice(df)
                
                # Show advice in a nice card
                st.markdown(f"""
                <div style="background-color: #1E1E1E; padding: 20px; border-radius: 10px; border-left: 5px solid #E63946;">
                    <h3 style="margin-top:0; color: #E63946;">🛡️ Coach Assessment</h3>
                    <p style="font-size: 1.1em; line-height: 1.5; color: #ddd;">{advice}</p>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("Log more workouts to unlock the Coach.")