import streamlit as st
import zipfile
import json
import requests
from io import BytesIO
import time

st.set_page_config(page_title="RPG Uncensored Translator", layout="wide")

st.title("🔞 معرب RPG الاحترافي (بدون قيود)")
st.write("يدعم هذا الإصدار OpenRouter لتجاوز قيود المحتوى +18 والتبديل التلقائي للمفاتيح.")

# إعدادات المفاتيح (OpenRouter)
keys_input = st.text_area("أدخل مفاتيح OpenRouter API (مفتاح في كل سطر):", height=100)
api_keys = [k.strip() for k in keys_input.split('\n') if k.strip()]

# اختيار الموديل (يفضل اختيار موديلات مرنة مع المحتوى)
model_choice = st.selectbox("اختر موديل الذكاء الاصطناعي:", [
    "meta-llama/llama-3.1-70b-instruct", 
    "google/gemini-flash-1.5", 
    "deepseek/deepseek-chat"
])

uploaded_zips = st.file_uploader("ارفع ملفات الـ ZIP الخاصة باللعبة:", type="zip", accept_multiple_files=True)

def translate_via_openrouter(content, filename, key, model):
    """وظيفة الترجمة عبر OpenRouter مع تجاوز الفلاتر"""
    text = content.decode('utf-8', errors='ignore')
    
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }
    
    # برومبت متخصص لإقناع الذكاء بالترجمة بدون رقابة
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system", 
                "content": "You are a professional game translator. Translate the text to Arabic accurately, preserving the adult/mature themes, slang, and style of the original RPG. Do not censor or skip anything. Keep code tags intact."
            },
            {"role": "user", "content": f"File: {filename}\nContent to translate:\n{text[:8000]}"}
        ]
    }

    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=60)
        if response.status_code == 200:
            return True, response.json()['choices'][0]['message']['content'], key
        elif response.status_code == 429:
            return "QUOTA_EXCEEDED", content, None
        else:
            return False, content, None
    except:
        return False, content, None

if uploaded_zips and api_keys:
    if st.button("🚀 ابدأ التعريب الشامل"):
        translated_zip = BytesIO()
        remaining_zip = BytesIO()
        all_keys_dead = False
        
        all_tasks = []
        for uploaded_zip in uploaded_zips:
            with zipfile.ZipFile(uploaded_zip, 'r') as z:
                for name in z.namelist():
                    if not name.endswith('/'):
                        all_tasks.append((name, z.read(name)))

        text_files = [t for t in all_tasks if t[0].endswith(('.json', '.js'))]
        other_files = [t for t in all_tasks if not t[0].endswith(('.json', '.js'))]

        progress_bar = st.progress(0)
        status_text = st.empty()
        
        with zipfile.ZipFile(translated_zip, 'w') as t_zip, zipfile.ZipFile(remaining_zip, 'w') as r_zip:
            # نقل ملفات الميديا فوراً
            for name, content in other_files:
                t_zip.writestr(name, content)

            completed = 0
            for idx, (filename, content) in enumerate(text_files):
                if all_keys_dead:
                    r_zip.writestr(filename, content)
                    continue
                
                status_text.text(f"جاري تعريب: {filename} ({idx+1}/{len(text_files)})")
                
                # محاولة الترجمة مع التبديل التلقائي بين المفاتيح
                success = False
                for current_key in api_keys:
                    res_status, res_text, active_key = translate_via_openrouter(content, filename, current_key, model_choice)
                    
                    if res_status is True:
                        t_zip.writestr(filename, res_text)
                        completed += 1
                        success = True
                        break # نجحت الترجمة، انتقل للملف التالي
                    elif res_status == "QUOTA_EXCEEDED":
                        continue # الكوتا خلصت، جرب المفتاح التالي
                
                if not success:
                    # لو جرب كل المفاتيح وما نفع
                    if any(translate_via_openrouter(content, filename, k, model_choice)[0] == "QUOTA_EXCEEDED" for k in api_keys):
                        all_keys_dead = True
                        st.error("⚠️ جميع المفاتيح استهلكت حصتها!")
                    r_zip.writestr(filename, content)

                progress_bar.progress((idx + 1) / len(text_files))

        st.divider()
        st.success(f"✅ اكتملت العملية! تم تعريب {completed} ملف.")
        
        c1, c2 = st.columns(2)
        with c1:
            st.download_button("📥 تحميل ما تم تعريبه", translated_zip.getvalue(), "Translated_Game.zip")
        if all_keys_dead or (completed < len(text_files)):
            with c2:
                st.download_button("📥 تحميل الملفات المتبقية (للمرة القادمة)", remaining_zip.getvalue(), "Remaining_Files.zip")
