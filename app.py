import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import google.generativeai as genai
import json
from datetime import datetime
import pandas as pd

# --- CONFIGURATION (MUST BE FIRST) ---
st.set_page_config(page_title="Gym AI", page_icon="🔥", layout="centered")

# --- CUSTOM CSS (THE MAKEUP) ---
st.markdown("""
    <style>
    /* 1. Make the App look like a Phone App */
    .stApp {
        background-color: #0E1117;
    }
    
    /* 2. Style the Tabs to look like Buttons */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #1E1E1E;
        border-radius: 4px 4px 0px 0px;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
        flex: 1; /* Make tabs equal width */
    }
    .stTabs [aria-selected="true"] {
        background-color: #E63946;
        color: white;
    }

    /* 3. Make Input Box look modern */
    .stTextArea textarea {
        background-color: #262730;
        color: white;
        border-radius: 12px;
        border: 1px solid #444;
    }

    /* 4. Make the Submit Button BIG and RED */
    .stButton > button {
        width: 100%;
        border-radius: 12px;
        height: 3em;
        background-color: #E63946;
        color: white;
        font-weight: bold;
        border: none;
    }
    .stButton > button:hover {
        background-color: #FF4B4B;
        color: white;
    }
    
    /* 5. Hide the default header/footer for immersion */
    header {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- SETUP (Same as before) ---
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

def parse_workout(text):
    MODEL_NAME = 'models/gemini-2.5-flash'
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        prompt = f"""
        Extract workout data from: "{text}".
        Return ONLY a JSON list with keys: "exercise" (Title Case), "weight" (int), "reps" (int), "notes".
        If weight is missing, use 0.
        """
        response = model.generate_content(prompt)
        cleaned_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(cleaned_text)
    except:
        return None

# --- UI HEADER ---
st.markdown("<h1 style='text-align: center; color: #E63946;'>🔥 XYDEN GYM</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #888;'>AI Powered • No Excuses</p>", unsafe_allow_html=True)

# --- TABS ---
tab1, tab2 = st.tabs(["📝 LOG WORKOUT", "📈 STATS"])

# ==========================================
# TAB 1: LOGGING
# ==========================================
with tab1:
    st.markdown("###") # Spacer
    with st.form("workout_form"):
        st.caption("Speak or type your set:")
        user_input = st.text_area("Input", height=100, label_visibility="collapsed",
                                  placeholder="e.g. Incline Bench 30kg 12 reps, 3 sets...")
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
                            item.get('notes', '')
                        ])
                    
                    ex_sheet.append_rows(rows)
                    st.cache_data.clear()
                    
                    # Success Card
                    st.success(f"🔥 Added {len(rows)} sets!")
                    
                    # Visual Preview Card
                    with st.container():
                        for item in workout_data:
                            st.markdown(f"""
                            <div style="background-color: #262730; padding: 10px; border-radius: 10px; margin-bottom: 5px; border-left: 5px solid #E63946;">
                                <strong style="color:white">{item['exercise']}</strong><br>
                                <span style="color:#aaa">{item['weight']}kg x {item['reps']} reps</span>
                            </div>
                            """, unsafe_allow_html=True)

                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.error("AI Missed that. Try again.")

# ==========================================
# TAB 2: ANALYTICS
# ==========================================
with tab2:
    st.markdown("###") # Spacer
    @st.cache_data(ttl=60)
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
        all_exercises = sorted(df['Exercise'].unique().tolist())
        selected = st.selectbox("Select Movement", all_exercises)
        
        subset = df[df['Exercise'] == selected].copy()
        subset['Weight'] = pd.to_numeric(subset['Weight'], errors='coerce')
        progress_df = subset.groupby('Date')['Weight'].max().reset_index()
        
        # METRICS ROW
        max_lift = progress_df['Weight'].max()
        last_lift = progress_df['Weight'].iloc[-1] if len(progress_df) > 0 else 0
        
        col1, col2 = st.columns(2)
        col1.metric("Personal Record", f"{max_lift} kg")
        col2.metric("Last Session", f"{last_lift} kg")
        
        # CHART
        st.line_chart(progress_df.set_index('Date'), color="#E63946")
        
    else:
        st.info("Start logging to see your stats!")