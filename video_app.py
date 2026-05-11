import streamlit as st
import whisper
import os
import asyncio
import edge_tts
import torch
import pandas as pd
import tempfile
from datetime import datetime
from moviepy import VideoFileClip, AudioFileClip, CompositeAudioClip
from deep_translator import GoogleTranslator

# --- ១. ការកំណត់ Cloud License (Google Sheets) ---
SHEET_ID = "1FnH6S0Dl7QecglYVE0vjWkJ3O-WU-SpH7-esPU34FfU"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

def check_license_online(email_input, key_input):
    try:
        df = pd.read_csv(CSV_URL, timeout=10)
        # សម្អាត Space និងប្តូរជាអក្សរតូចដើម្បីកុំឱ្យខុសពេល Login
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
        return False, f"⚠️ មិនអាចភ្ជាប់ទៅកាន់ Server: {str(e)}"

async def generate_voice(text, voice_name, output_path):
    communicate = edge_tts.Communicate(text, voice_name)
    await communicate.save(output_path)

# --- ២. រៀបចំ UI និង Login ---
st.set_page_config(page_title="Zenzu Video AI Pro", page_icon="🎬", layout="wide")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔐 Zenzu AI Studio - Login System")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        email = st.text_input("អ៊ីមែល (Email)")
        p_key = st.text_input("លេខកូដសម្ងាត់ (Key Code)", type="password")
        
        if st.button("ចូលប្រើប្រាស់"):
            if email and p_key:
                success, message = check_license_online(email, p_key)
                if success:
                    st.session_state.logged_in = True
                    st.session_state.current_user = email
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
    st.stop()

# --- ៣. ផ្នែកផលិតវីដេអូ ---
st.sidebar.title("🎨 Zenzu Studio")
st.sidebar.success(f"👤 {st.session_state.current_user}")

languages = {"ខ្មែរ 🇰🇭": "km", "English 🇺🇸": "en", "ចិន 🇨🇳": "zh-CN"}
target_lang_label = st.sidebar.selectbox("បកប្រែទៅជាភាសា", list(languages.keys()))
target_code = languages[target_lang_label]

voice_map = {"km": "km-KH-SreymomNeural", "en": "en-US-JennyNeural", "zh-CN": "zh-CN-XiaoxiaoNeural"}

st.title("🎬 Video AI Studio")
uploaded_file = st.file_uploader("Upload MP4 Video", type=["mp4"])

if uploaded_file and st.button("🚀 ចាប់ផ្តើមផលិត"):
    with st.status("🛠️ AI កំពុងដំណើរការ...", expanded=True) as status:
        # ប្រើ tempfile ដើម្បីដោះស្រាយបញ្ហា FileNotFoundError លើ Cloud
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tfile:
            tfile.write(uploaded_file.getbuffer())
            input_path = tfile.name

        try:
            st.write("🔍 កំពុងស្កេនសំឡេង (Fast Mode)...")
            device = "cuda" if torch.cuda.is_available() else "cpu"
            model = whisper.load_model("base", device=device)
            result = model.transcribe(input_path, fp16=False)
            
            st.write("🌐 កំពុងបកប្រែអត្ថបទ...")
            translated_text = GoogleTranslator(source='auto', target=target_code).translate(result['text'])

            st.write("🎙️ កំពុងបង្កើតសំឡេង AI...")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as out_audio:
                audio_path = out_audio.name
            v_id = voice_map.get(target_code, "en-US-JennyNeural")
            asyncio.run(generate_voice(translated_text, v_id, audio_path))

            st.write("🎬 កំពុង Rendering (Ultrafast Mode)...")
            video = VideoFileClip(input_path)
            audio_ai = AudioFileClip(audio_path)
            
            # បញ្ចូលសំឡេង AI ទៅក្នុងវីដេអូ
            final_video = video.set_audio(audio_ai)
            output_final = "zenzu_output.mp4"
            
            # threads=4 និង preset="ultrafast" ជួយឱ្យលឿនបំផុតលើ Cloud
            final_video.write_videofile(
                output_final, 
                codec="libx264", 
                audio_codec="aac", 
                fps=24, 
                preset="ultrafast", 
                threads=4
            )
            
            st.success("✨ រួចរាល់!")
            st.video(output_final)
            
            with open(output_final, "rb") as f:
                st.download_button("📥 ទាញយកវីដេអូ", f, file_name="zenzu_ai_video.mp4")

        except Exception as e:
            st.error(f"❌ កើតបញ្ហា៖ {str(e)}")
        finally:
            # លុបហ្វាលបណ្ដោះអាសន្ន
            if os.path.exists(input_path): os.remove(input_path)
            if 'audio_path' in locals() and os.path.exists(audio_path): os.remove(audio_path)
