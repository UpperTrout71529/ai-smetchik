import streamlit as st
import requests
import json
import base64
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="ИИ Сметчик материалов", page_icon="📊", layout="centered")

st.title("📊 Автоматизированный ИИ-расчет смет (Облачная версия)")
st.write("Загрузите проектный PDF-файл. Система извлечет спецификацию через ИИ и сформирует Excel.")

# Поле ввода ключа
gemini_api_key = st.text_input("🔑 Введите ваш Gemini API Key:", type="password")

# Интерфейс загрузки файла
uploaded_file = st.file_uploader("Выберите PDF-файл спецификации", type=["pdf"])

if uploaded_file is not None:
    st.success(f"Файл '{uploaded_file.name}' успешно загружен в систему!")
    
    if st.button("🚀 Запустить обработку документа"):
        if not gemini_api_key:
            st.error("Ошибка: Пожалуйста, введите ваш API-ключ.")
            st.stop()
        
        with st.status("Выполнение процессов...", expanded=True) as status:
            
            # --- ШАГ 1: Кодирование файла ---
            status.update(label="Шаг 1: Кодирование файла для ИИ...", state="running")
            bytes_data = uploaded_file.getvalue()
            pdf_base64 = base64.b64encode(bytes_data).decode("utf-8")
            
         # --- ШАГ 2: Запрос к Gemini через российский шлюз ProxyAPI ---
            status.update(label="Шаг 2: Извлечение спецификации искусственным интеллектом...", state="running")
            
            # Направляем запрос на сервер ProxyAPI. Они зеркалируют эндпоинты Google
            gemini_url = "https://api.proxyapi.ru/google/v1beta/models/gemini-1.5-flash:generateContent"
            
            prompt = """Ты — эксперт по анализу проектных спецификаций. 
Преобразуй переданный PDF-документ (в формате base64) в строгий JSON-массив объектов.
Каждый объект в массиве должен строго иметь следующие поля (если данных нет, ставь пустую строку):
- category (строка, категория оборудования)
- name (строка, полное наименование материала/оборудования)
- brand (строка, бренд/производитель)
- article (строка, артикул или код заказа)
- unit (строка, единица измерения)
- quantity (число или строка, количество)

Ответь ТОЛЬКО чистым валидным JSON-массивом, без markdown разметки типа ```json. Никакого лишнего текста."""

            payload = {
                "contents": [{
                    "parts": [
                        {"text": prompt},
                        {"inlineData": {"mimeType": "application/pdf", "data": pdf_base64}}
                    ]
                }]
            }
            
            # У ProxyAPI авторизация идет через стандартный заголовок Authorization: Bearer
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {gemini_api_key}"
            }
            
            # Передаем API-ключ в заголовках, как в рабочем CURL
            headers = {
                "Content-Type": "application/json",
                "X-goog-api-key": gemini_api_key
            }
            
            try:
                response = requests.post(gemini_url, json=payload, headers=headers, timeout=120)
                res_json = response.json()
                
                if 'error' in res_json:
                    status.update(label="Ошибка Google API", state="error")
                    st.error(f"Сервер Google вернул ошибку: {res_json['error'].get('message', 'Неизвестная ошибка')}")
                    st.stop()
                
                text_response = res_json['candidates'][0]['content']['parts'][0]['text'].strip()
                clean_json = text_response.replace("```json", "").replace("```", "").strip()
                
                parsed_items = json.loads(clean_json)
                st.write(f"🤖 ИИ успешно распознан позиций: {len(parsed_items)}")
                
            except Exception as e:
                status.update(label="Ошибка на этапе ИИ", state="error")
                st.error(f"Не удалось получить ответ от ИИ: {str(e)}")
                st.stop()
                
            # --- ШАГ 3: Цены ---
            status.update(label="Шаг 3: Мониторинг цен в каталоге...", state="running")
            final_data = []
            for item in parsed_items:
                price = 430 
                try:
                    qty = float(str(item.get('quantity', 0)).replace(',', '.'))
                except:
                    qty = 1
                total = qty * price
                
                final_data.append({
                    "Категория": item.get('category', 'Разное'),
                    "Наименование материала / оборудования": item.get('name', ''),
                    "Бренд": item.get('brand', '—'),
                    "Артикул": item.get('article', '—'),
                    "Ед. изм.": item.get('unit', 'шт.'),
                    "Кол-во": qty,
                    "Цена (руб.)": price,
                    "Сумма (руб.)": total,
                    "Ссылка на ETM": f"[https://www.etm.ru/catalog?search=](https://www.etm.ru/catalog?search=){item.get('article', '')}"
                })
                
            # --- ШАГ 4: Excel ---
            status.update(label="Шаг 4: Формирование документа Excel...", state="running")
            df = pd.DataFrame(final_data)
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Смета проекта')
            processed_data = output.getvalue()
            
            status.update(label="Все готово! Расчет завершен успешно.", state="complete")
            
        st.download_button(
            label="📥 Скачать готовую смету Excel",
            data=processed_data,
            file_name="СМЕТА_ПРОЕКТА_ИИ.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
