import streamlit as st
import whisper
import os
import asyncio
import edge_tts
import json
import torch
import pandas as pd
import tempfile  # បន្ថែមដើម្បីដោះស្រាយបញ្ហា File Error
from datetime import timedelta
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip, CompositeVideoClip, ImageClip
from deep_translator import GoogleTranslator

# --- ១. ការកំណត់ Cloud License (Google Sheets) ---
SHEET_ID = "1FnH6S0Dl7QecglYVE0vjWkJ3O-WU-SpH7-esPU34FfU"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

def check_license_online(email_input, key_input):
    try:
        df = pd.read_csv(CSV_URL)
        user = df[(df['email'] == email_input) & (df['key'].astype(str) == key_input)]
        
        if not user.empty:
            status = str(user.iloc[0]['status']).strip().lower()
            expiry_str = str(user.iloc[0]['expiry']).strip()
            # ទាញយក Role ពី Sheets (admin/user)
            role = str(user.iloc[0]['role']).strip().lower() if 'role' in df.columns else 'user'
            
            expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d").date()
            
            if status != "active":
                return False, "❌ គណនីរបស់អ្នកត្រូវបានផ្អាក!", "user"
            if datetime.now().date() > expiry_date:
                return False, f"⏰ Key របស់អ្នកផុតកំណត់ហើយ!", "user"
            return True, "✅ ជោគជ័យ!", role
        return False, "❌ អ៊ីមែល ឬ Key មិនត្រឹមត្រូវ!", "user"
    except:
        return False, "⚠️ មិនអាចភ្ជាប់ទៅកាន់ Server បានទេ", "user"

async def generate_voice(text, voice_name, output_path, speed):
    rate = f"{'+' if speed >= 1.0 else '-'}{int(abs(speed-1)*100)}%"
    communicate = edge_tts.Communicate(text, voice_name, rate=rate)
    await communicate.save(output_path)

# --- ២. រៀបចំ UI និងប្រព័ន្ធ Login ---
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
                success, message, role = check_license_online(email, p_key)
                if success:
                    st.session_state.logged_in = True
                    st.session_state.current_user = email
                    st.session_state.user_role = role
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
    st.stop()

# --- ៣. ផ្នែក Sidebar ---
st.sidebar.title("🎨 Zenzu Custom Studio")
st.sidebar.success(f"👤 {st.session_state.current_user} ({st.session_state.user_role})")

st.sidebar.subheader("⚙️ កម្រិតច្បាស់វីដេអូ")
res_options = {"360p": (640, 360), "720p": (1280, 720), "1080p": (1920, 1080)}
selected_res = st.sidebar.selectbox("ជ្រើសរើស Resolution", list(res_options.keys()), index=1)
target_res = res_options[selected_res]

st.sidebar.subheader("🌐 ការកំណត់ភាសាបកប្រែ")
languages = {"ខ្មែរ 🇰🇭": "km", "English 🇺🇸": "en", "ចិន 🇨🇳": "zh-CN"}
target_lang_label = st.sidebar.selectbox("បកប្រែទៅជាភាសា", list(languages.keys()))
target_code = languages[target_lang_label]

voice_map = {"km": "km-KH-SreymomNeural", "en": "en-US-JennyNeural", "zh-CN": "zh-CN-XiaoxiaoNeural"}

menu = ["ផលិតវីដេអូ"]
if st.session_state.get('user_role') == "admin":
    menu.append("Admin Panel")

choice = st.sidebar.selectbox("ម៉ឺនុយ", menu)

if st.sidebar.button("ចាកចេញ (Logout)"):
    st.session_state.logged_in = False
    st.rerun()

# --- ៤. ផ្ទាំងផលិតវីដេអូ ---
if choice == "ផលិតវីដេអូ":
    st.title(f"🎬 Video AI Studio ({selected_res})")
    
    logo_file = st.sidebar.file_uploader("Upload Logo", type=["png", "jpg"])
    bgm_file = st.sidebar.file_uploader("បញ្ចូលភ្លេង BGM", type=["mp3"])
    bgm_vol = st.sidebar.slider("កម្រិតសំឡេងភ្លេង (%)", 0, 50, 10)
    uploaded_file = st.file_uploader("Upload MP4 Video", type=["mp4"])

    if uploaded_file and st.button("🚀 ចាប់ផ្តើមផលិត"):
        with st.status("🛠️ AI កំពុងដំណើរការ...", expanded=True) as status:
            # កែសម្រួល៖ ប្រើ tempfile ដើម្បីបំបាត់ FileNotFoundError
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tfile:
                tfile.write(uploaded_file.getbuffer())
                input_path = tfile.name

            try:
                st.write("🔍 កំពុងស្កេនសំឡេង (Fast Mode)...")
                device = "cuda" if torch.cuda.is_available() else "cpu"
                model = whisper.load_model("base", device=device) # ប្រើ model 'base' ដើម្បីឱ្យលឿន
                result = model.transcribe(input_path, fp16=False)
                
                st.write("🌐 កំពុងបកប្រែអត្ថបទ...")
                translated_text = GoogleTranslator(source='auto', target=target_code).translate(result['text'])

                st.write(f"🎙️ កំពុងបង្កើតសំឡេង AI...")
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as out_audio:
                    output_audio_path = out_audio.name
                
                v_id = voice_map.get(target_code, "en-US-JennyNeural")
                asyncio.run(generate_voice(translated_text, v_id, output_audio_path, 1.0))

                st.write(f"🎬 កំពុង Rendering (Preset: Ultrafast)...")
                video = VideoFileClip(input_path).resized(width=target_res[0])
                audio_ai = AudioFileClip(output_audio_path)
                
                audio_layers = [audio_ai]
                if bgm_file:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as bfile:
                        bfile.write(bgm_file.getbuffer())
                        bgm_path = bfile.name
                    bgm = AudioFileClip(bgm_path).set_duration(video.duration).volumex(bgm_vol/100)
                    audio_layers.append(bgm)

                final_video = video.set_audio(CompositeAudioClip(audio_layers))
                
                # បង្កើនល្បឿន Render ដោយប្រើ threads និង preset ultrafast
                output_final = "zenzu_final.mp4"
                final_video.write_videofile(output_final, codec="libx264", audio_codec="aac", fps=24, preset="ultrafast", threads=4)
                
                st.success("✨ រួចរាល់!")
                st.video(output_final)
                
                with open(output_final, "rb") as f:
                    st.download_button("📥 ទាញយកវីដេអូ", f, file_name="zenzu_video.mp4")

            except Exception as e:
                st.error(f"❌ បញ្ហាត្រង់៖ {str(e)}")
            finally:
                # សម្អាត File ក្រោយប្រើចប់
                if os.path.exists(input_path): os.remove(input_path)

elif choice == "Admin Panel":
    st.title("👥 គ្រប់គ្រងអ្នកប្រើប្រាស់")
    df = pd.read_csv(CSV_URL)
    st.dataframe(df)
