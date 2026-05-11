import streamlit as st
import whisper
import os
import asyncio
import edge_tts
import torch
import pandas as pd
import tempfile
from datetime import datetime
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip
from deep_translator import GoogleTranslator

# --- ១. ការកំណត់ Cloud License (Google Sheets) ---
SHEET_ID = "1FnH6S0Dl7QecglYVE0vjWkJ3O-WU-SpH7-esPU34FfU"
# ប្រើផ្លូវនេះដើម្បីទាញយក CSV ឱ្យបានត្រឹមត្រូវ
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

def check_license_online(email_input, key_input):
    try:
        # ដក timeout ចេញដើម្បីកុំឱ្យមាន Error ដូចក្នុងរូបភាព image_9744ee.png
        df = pd.read_csv(CSV_URL)
        email_input = email_input.strip().lower()
        key_input = str(key_input).strip()
        
        user = df[(df['email'].str.strip().str.lower() == email_input) & 
                  (df['key'].astype(str).str.strip() == key_input)]
        
        if not user.empty:
            status = str(user.iloc[0]['status']).strip().lower()
            expiry_str = str(user.iloc[0]['expiry']).strip()
            expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d").date()
            
            if status != "active":
                return False, "❌ គណនីរបស់អ្នកត្រូវបានផ្អាក!"
            if datetime.now().date() > expiry_date:
                return False, "⏰ Key របស់អ្នកផុតកំណត់ហើយ!"
            return True, "✅ ជោគជ័យ!"
        return False, "❌ អ៊ីមែល ឬ Key មិនត្រឹមត្រូវ!"
    except Exception as e:
        return False, f"⚠️ មិនអាចភ្ជាប់ទៅកាន់ Server បានទេ"

async def generate_voice(text, voice_name, output_path):
    communicate = edge_tts.Communicate(text, voice_name)
    await communicate.save(output_path)

# --- ២. ប្រព័ន្ធ Login ---
st.set_page_config(page_title="Zenzu Video AI Pro", layout="wide")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔐 Zenzu AI Studio - Login System")
    email = st.text_input("Email")
    p_key = st.text_input("Key Code", type="password")
    if st.button("ចូលប្រើប្រាស់"):
        success, message = check_license_online(email, p_key)
        if success:
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error(message)
    st.stop()

# --- ៣. ផ្ទាំងផលិតវីដេអូ ---
st.title("🎬 Video AI Studio")
uploaded_file = st.file_uploader("Upload MP4 Video", type=["mp4"])

if uploaded_file and st.button("🚀 ចាប់ផ្តើមផលិត"):
    with st.status("🛠️ AI កំពុងដំណើរការ...", expanded=True):
        # ប្រើ tempfile ដើម្បីដោះស្រាយ FileNotFoundError (រូបភាព image_085dfc.jpg)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tfile:
            tfile.write(uploaded_file.getbuffer())
            input_path = tfile.name

        try:
            # ១. បំប្លែងសំឡេងជាអត្ថបទ
            model = whisper.load_model("base")
            result = model.transcribe(input_path)
            
            # ២. បកប្រែជាភាសាខ្មែរ
            translated_text = GoogleTranslator(source='auto', target='km').translate(result['text'])

            # ៣. បង្កើតសំឡេង AI
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as out_audio:
                audio_path = out_audio.name
            asyncio.run(generate_voice(translated_text, "km-KH-SreymomNeural", audio_path))

            # ៤. រួមបញ្ចូលវីដេអូ (ដោះស្រាយ ffmpeg error ក្នុងរូបភាព image_078c5f.png)
            video = VideoFileClip(input_path)
            audio_ai = AudioFileClip(audio_path)
            final_video = video.set_audio(audio_ai)
            
            output_name = "zenzu_final.mp4"
            final_video.write_videofile(output_name, codec="libx264", audio_codec="aac", preset="ultrafast")
            
            st.video(output_name)
            st.success("✨ ផលិតរួចរាល់!")
            
        except Exception as e:
            st.error(f"❌ បញ្ហា៖ {str(e)}")
        finally:
            # លុបហ្វាលបណ្ដោះអាសន្នចេញ
            if os.path.exists(input_path): os.remove(input_path)
