import streamlit as st
import zipfile
import json
import requests
from io import BytesIO
import arabic_reshaper
from bidi.algorithm import get_display
from concurrent.futures import ThreadPoolExecutor

# --- إعدادات الواجهة ---
st.set_page_config(page_title="RPG Arabic Ultimate", layout="wide", page_icon="🔞")

# --- دالة إصلاح العربي (حل مشكلة الحروف المعكوسة) ---
def fix_arabic_logic(text):
    if not text or not any(ord(char) > 127 for char in text):
        return text
    try:
        # تشبيك الحروف العربية ثم قلب الاتجاه ليناسب محرك RPG Maker
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)
    except:
        return text

# --- إدارة المفاتيح الديناميكية في الشريط الجانبي ---
if 'api_keys' not in st.session_state:
    st.session_state.api_keys = [""]

def add_key(): st.session_state.api_keys.append("")
def remove_key(index): st.session_state.api_keys.pop(index)

with st.sidebar:
    st.header("⚙️ لوحة التحكم والمفاتيح")
    for i, key in enumerate(st.session_state.api_keys):
        col_k, col_d = st.columns([0.8, 0.2])
        st.session_state.api_keys[i] = col_k.text_input(f"مفتاح OpenRouter {i+1}", value=key, type="password")
        if col_d.button("❌", key=f"del_{i}"):
            remove_key(i)
            st.rerun()
    st.button("➕ إضافة مفتاح جديد", on_click=add_key)
    
    st.divider()
    speed = st.slider("🚀 سرعة المعالجة (Parallel Threads)", 1, 15, 5)
    model_choice = st.selectbox("🤖 الموديل المفضل", [
        "meta-llama/llama-3.1-70b-instruct", 
        "google/gemini-flash-1.5", 
        "deepseek/deepseek-chat"
    ])

# --- محرك الترجمة الأساسي ---
def translate_core(content, filename, key):
    try:
        text = content.decode('utf-8', errors='ignore')
        
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://streamlit.io", # متطلب لبعض موديلات OpenRouter
        }
        
        # برومبت تخطي الرقابة والحفاظ على الأكواد التقنية
        payload = {
            "model": model_choice,
            "messages": [
                {
                    "role": "system", 
                    "content": "You are a professional RPG game localizer. Translate to Arabic. IMPORTANT: Translate all adult themes, slang, and mature content without any censorship. Keep technical tags like \\V[n], \\N[n], <...>, and {...} exactly as they are."
                },
                {"role": "user", "content": f"File: {filename}\nTranslate this:\n\n{text}"}
            ]
        }

        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=60)
        
        if response.status_code == 200:
            translated_text = response.json()['choices'][0]['message']['content']
            # معالجة النص ليكون صحيحاً (RTL)
            return fix_arabic_logic(translated_text), True
        else:
            return text, False # فشل (غالباً كوتا أو خطأ سيرفر)
    except Exception:
        return content.decode('utf-8', errors='ignore'), False

# --- التطبيق الرئيسي ---
st.title("🔞 معرب RPG الشامل V3 (الأسرع والأذكى)")
st.write("ارفع ملفات الـ ZIP، وزع مفاتيحك، واترك الباقي لي.")

uploaded_zips = st.file_uploader("ارفع ملفات ZIP اللعبة (يمكنك رفع عدة ملفات):", type="zip", accept_multiple_files=True)

if uploaded_zips and any(st.session_state.api_keys):
    if st.button("🔥 ابدأ عملية التعريب الكبرى"):
        valid_keys = [k for k in st.session_state.api_keys if k]
        
        final_zip_mem = BytesIO() # الملف اللي فيه كل شيء (المترجم + الأصلي لو فشل)
        remaining_zip_mem = BytesIO() # الملف اللي فيه "فقط" اللي ما تترجم
        
        all_text_tasks = []
        failed_count = 0
        
        with zipfile.ZipFile(final_zip_mem, 'w') as out_zip, \
             zipfile.ZipFile(remaining_zip_mem, 'w') as rem_zip:
            
            # 1. جمع الملفات من كل الـ ZIPs المرفوعة
            for uploaded_zip in uploaded_zips:
                with zipfile.ZipFile(uploaded_zip, 'r') as z:
                    for name in z.namelist():
                        if name.endswith(('.json', '.js')):
                            all_text_tasks.append((name, z.read(name)))
                        elif not name.endswith('/'):
                            # ملفات الميديا والخطوط تنقل فوراً للملف النهائي
                            out_zip.writestr(name, z.read(name))

            # 2. الترجمة المتوازية باستخدام الـ Threads
            progress = st.progress(0)
            status_text = st.empty()
            
            with ThreadPoolExecutor(max_workers=speed) as executor:
                futures = []
                for idx, task in enumerate(all_text_tasks):
                    # توزيع المفاتيح بالتناوب (Round Robin)
                    current_key = valid_keys[idx % len(valid_keys)]
                    futures.append(executor.submit(translate_core, task[1], task[0], current_key))
                
                for idx, (future, task) in enumerate(zip(futures, all_text_tasks)):
                    result_text, is_success = future.result()
                    
                    # نضع النتيجة (سواء ترجمت أو لا) في الملف النهائي عشان اللعبة تشتغل
                    out_zip.writestr(task[0], result_text)
                    
                    if not is_success:
                        failed_count += 1
                        # نضع الملف "الأصلي" في ملف المتبقيات عشان تعيد ترجمته لاحقاً
                        rem_zip.writestr(task[0], task[1])
                    
                    progress.progress((idx + 1) / len(all_text_tasks))
                    status_text.text(f"جاري معالجة: {task[0]} ({idx+1}/{len(all_text_tasks)})")

        st.divider()
        st.success(f"✅ انتهت العملية! تم تعريب {len(all_text_tasks) - failed_count} ملف بنجاح.")
        
        # عرض أزرار التحميل
        col1, col2 = st.columns(2)
        
        with col1:
            st.info("تحميل اللعبة كاملة (المترجم + الباقي كما هو)")
            st.download_button("📥 تحميل اللعبة المعربة", final_zip_mem.getvalue(), "Arabic_Game_Full.zip")
            
        if failed_count > 0:
            with col2:
                st.warning(f"يوجد {failed_count} ملف لم يترجم (خلصت التوكنات؟)")
                st.download_button("📥 تحميل المتبقيات فقط (للمرة القادمة)", remaining_zip_mem.getvalue(), "Remaining_Files.zip")
else:
    if not uploaded_zips:
        st.info("💡 بانتظار رفع ملفات الـ ZIP...")
    if not any(st.session_state.api_keys):
        st.error("🔑 يرجى إضافة مفتاح API واحد على الأقل من القائمة الجانبية.")
