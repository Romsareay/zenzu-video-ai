import streamlit as st
import whisper
import os
import asyncio
import edge_tts
import json
import torch # បន្ថែមដើម្បីឆែកល្បឿន GPU
import pandas as pd
from datetime import datetime, timedelta
from moviepy import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, ImageClip
from moviepy.audio.AudioClip import CompositeAudioClip
from deep_translator import GoogleTranslator

# --- ១. ការកំណត់ Cloud License (Google Sheets) ---
SHEET_ID = "1FnH6S0Dl7QecglYVE0vjWkJ3O-WU-SpH7-esPU34FfU"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

def check_license_online(email_input, key_input):
    try:
        # ទាញទិន្នន័យពី Google Sheets មកផ្ទៀងផ្ទាត់
        df = pd.read_csv(CSV_URL)
        user = df[(df['email'] == email_input) & (df['key'].astype(str) == key_input)]
        
        if not user.empty:
            status = str(user.iloc[0]['status']).strip().lower()
            expiry_str = str(user.iloc[0]['expiry']).strip()
            expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d").date()
            
            if status != "active":
                return False, "❌ គណនីរបស់អ្នកត្រូវបានផ្អាក!"
            if datetime.now().date() > expiry_date:
                return False, f"⏰ Key របស់អ្នកផុតកំណត់ហើយ!"
            return True, "✅ ជោគជ័យ!"
        return False, "❌ អ៊ីមែល ឬ Key មិនត្រឹមត្រូវ!"
    except:
        return False, "⚠️ មិនអាចភ្ជាប់ទៅកាន់ Server បានទេ (សូមឆែកអ៊ីនធឺណិត)"

# --- ២. ការកំណត់ផ្លូវសម្រាប់ ImageMagick (ប្រសិនបើចាំបាច់) ---
os.environ["IMAGEMAGICK_BINARY"] = r"C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\magick.exe"

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
                # ហៅប្រើ Function ថ្មីដែលអ្នកបានសរសេរនៅខាងលើ
                success, message = check_license_online(email, p_key)
                
                if success:
                    st.session_state.logged_in = True
                    st.session_state.current_user = email
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
            else:
                st.warning("⚠️ សូមបំពេញអ៊ីមែល និងលេខកូដសម្ងាត់!")
    st.stop()

# --- ៣. ផ្នែក Sidebar ---
st.sidebar.title("🎨 Zenzu Custom Studio")
st.sidebar.success(f"👤 {st.session_state.current_user}")

# កន្លែងរើសកម្រិតវីដេអូ
st.sidebar.subheader("⚙️ កម្រិតច្បាស់វីដេអូ")
res_options = {
    "360p": (640, 360),
    "720p": (1280, 720),
    "1080p (Full HD)": (1920, 1080),
    "2K": (2560, 1440),
    "4K": (3840, 2160)
}
selected_res = st.sidebar.selectbox("ជ្រើសរើស Resolution", list(res_options.keys()), index=2)
target_res = res_options[selected_res]

# --- ៤. ការកំណត់ភាសា (ខ្មែរ ចិន កូរ៉េ ជប៉ុន អង់គ្លេស) ---
st.sidebar.subheader("🌐 ការកំណត់ភាសាបកប្រែ")
languages = {
    "ខ្មែរ 🇰🇭": "km",
    "English 🇺🇸": "en",
    "ចិន 🇨🇳": "zh-CN",
    "កូរ៉េ 🇰🇷": "ko",
    "ជប៉ុន 🇯🇵": "ja"
}

# ជ្រើសរើសភាសាដើម និងភាសាគោលដៅ
source_lang = st.sidebar.selectbox("ភាសាដើមក្នុងវីដេអូ", ["ស្វែងរកអូតូ (Auto)"] + list(languages.keys()))
target_lang_label = st.sidebar.selectbox("បកប្រែទៅជាភាសា", list(languages.keys()))

source_code = "auto" if source_lang == "ស្វែងរកអូតូ (Auto)" else languages[source_lang]
target_code = languages[target_lang_label]

# កំណត់សំឡេង AI តាមភាសាគោលដៅ
voice_map = {
    "km": "km-KH-SreymomNeural",
    "en": "en-US-JennyNeural",
    "zh-CN": "zh-CN-XiaoxiaoNeural",
    "ko": "ko-KR-SunHiNeural",
    "ja": "ja-JP-NanamiNeural"
}

menu = ["ផលិតវីដេអូ"]
if st.session_state.get('user_role') == "admin":
    menu.append("គ្រប់គ្រងអ្នកប្រើប្រាស់ (Admin)")

choice = st.sidebar.selectbox("ម៉ឺនុយ", menu)

if st.sidebar.button("ចាកចេញ (Logout)"):
    st.session_state.logged_in = False
    st.rerun()

# --- ៥. ផ្ទាំងផលិតវីដេអូ ---
if choice == "ផលិតវីដេអូ":
    st.title(f"🎬 Video AI Studio ({selected_res})")
    
    logo_file = st.sidebar.file_uploader("Upload Logo", type=["png", "jpg"])
    bgm_file = st.sidebar.file_uploader("បញ្ចូលភ្លេង BGM", type=["mp3"])
    bgm_vol = st.sidebar.slider("កម្រិតសំឡេងភ្លេង (%)", 0, 50, 10)
    
    # បង្កើនទំហំ Upload ក្នុង UI
    uploaded_file = st.file_uploader("Upload MP4 Video (Max 2000MB)", type=["mp4"])

    if uploaded_file and st.button("🚀 ចាប់ផ្តើមផលិត"):
        with st.status("🛠️ AI កំពុងដំណើរការ (High Speed Mode)...", expanded=True) as status:
            with open("input_temp.mp4", "wb") as f: f.write(uploaded_file.getbuffer())
            
            # --- បង្កើនល្បឿនដោយប្រើ Turbo/Base Model និង GPU ប្រសិនបើមាន ---
            st.write("🔍 កំពុងបកប្រែអត្ថបទ (Fast Mode)...")
            device = "cuda" if torch.cuda.is_available() else "cpu"
            model = whisper.load_model("base", device=device) # ប្រើ model 'base' ដើម្បីឱ្យលឿន
            
            result = model.transcribe("input_temp.mp4", fp16=False)
            
            # បកប្រែដោយប្រើ Google Translator
            translated_text = GoogleTranslator(source=source_code, target=target_code).translate(result['text'])

            st.write(f"🎙️ កំពុងបង្កើតសំឡេង AI ({target_lang_label})...")
            v_id = voice_map.get(target_code, "en-US-JennyNeural")
            asyncio.run(generate_voice(translated_text, v_id, "output_audio.mp3", 1.0))

            st.write(f"🎬 កំពុង Rendering វីដេអូក្នុងកម្រិត {selected_res}...")
            # ប្រើ threads ដើម្បីឱ្យ rendering លឿនជាងមុន
            video = VideoFileClip("input_temp.mp4").resized(width=target_res[0])
            
            audio_ai = AudioFileClip("output_audio.mp3")
            audio_layers = [audio_ai]
            
            if bgm_file:
                with open("bgm_temp.mp3", "wb") as f: f.write(bgm_file.getbuffer())
                bgm = AudioFileClip("bgm_temp.mp3").with_duration(video.duration).volumex(bgm_vol / 100)
                audio_layers.append(bgm)
            
            video_final = video.with_audio(CompositeAudioClip(audio_layers))
            elements = [video_final]

            if logo_file:
                with open("logo_temp.png", "wb") as f: f.write(logo_file.getbuffer())
                logo = (ImageClip("logo_temp.png").with_duration(video.duration)
                        .resized(width=target_res[0]//10).with_position(("right", "top")))
                elements.append(logo)

            try:
                f_size = target_res[1] // 20
                # ប្តូរ Font តាមភាសាដើម្បីកុំឱ្យបែកអក្សរ (Arial គាំទ្រ ចិន កូរ៉េ ជប៉ុន បានល្អ)
                selected_font = 'Leelawadee-UI' if target_code == 'km' else 'Arial'
                
                txt = (TextClip(text=translated_text, font_size=f_size, color='white', 
                                font=selected_font, method='caption', size=(int(video.w * 0.8), None))
                       .with_duration(video.duration).with_position(("center", "bottom")))
                elements.append(txt)
            except: pass

            final_clip = CompositeVideoClip(elements)
            b_rate = "15M" if "4K" in selected_res else "8M" if "2K" in selected_res else "4M"
            
            # --- បង្កើនល្បឿន Rendering ដោយប្រើ threads ---
            final_clip.write_videofile(
                "zenzu_final.mp4", 
                codec="libx264", 
                audio_codec="aac", 
                fps=24, 
                bitrate=b_rate,
                threads=4, # ប្រើ CPU ៤ គ្រាប់ដើម្បីឱ្យលឿន
                preset="ultrafast" # កំណត់ឱ្យ render លឿនបំផុត
            )
            status.update(label="✨ រួចរាល់!", state="complete")

        

elif choice == "គ្រប់គ្រងអ្នកប្រើប្រាស់ (Admin)":
    # (ផ្នែក Admin Panel រក្សាទុកដូចដើម...)
    st.title("👥 ផ្ទាំងគ្រប់គ្រងអ្នកប្រើប្រាស់")
    # ...
