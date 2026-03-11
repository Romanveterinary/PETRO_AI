import flet as ft
import os
import datetime
import base64
import requests
import json
import traceback

# 1. БАЗОВИЙ API КЛЮЧ (ПУСТИЙ ДЛЯ БЕЗПЕКИ НА GITHUB)
DEFAULT_API_KEY = ""

# 2. СИСТЕМНИЙ ПРОМПТ (PETROVET 49.0)
system_instruction = """
Ти — провідний ветеринарно-санітарний інспектор-аналітик України. 
Твоя спеціалізація — контроль безпечності харчових продуктів.
База знань: Накази №16, №46, №28, №57, №1032, Закони №1870-IV, №771, КУпАП (ст. 107, 160).
ПРАВИЛО ПРІОРИТЕТУ: Якщо людина-інспектор передає коментар "Недоліків немає" або подібний, 
ти ПОВИНЕН погодитися з ним, встановити ЗЕЛЕНИЙ рівень ризику і не шукати порушень.

ОБОВ'ЯЗКОВИЙ АНАЛІЗ: 
Завжди оцінюй гігієну продавців, стан місця для продажу, чистоту поверхонь, стан ножів/інвентарю та наявність рукавичок. 
Описуй порушення по пунктах із суворим посиланням на відповідне законодавство (наприклад, Наказ №16).
"""

# --- БЕЗПЕЧНІ ШЛЯХИ ДЛЯ ПК ТА АНДРОЇД ---
safe_dir = os.environ.get("FLET_APP_STORAGE", ".") 
KEY_FILE = os.path.join(safe_dir, "api_key_market.txt")
REPORTS_DIR = "/storage/emulated/0/Download"
try:
    if not os.path.exists(REPORTS_DIR): REPORTS_DIR = safe_dir
except: REPORTS_DIR = safe_dir

def get_saved_api_key():
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "r") as f:
            return f.read().strip()
    return None

def save_api_key_to_file(key):
    with open(KEY_FILE, "w") as f:
        f.write(key)

def main(page: ft.Page):
    try:
        page.title = "VET-INSPECTOR AUDIT PRO"
        page.window_width = 450
        page.window_height = 850
        page.scroll = ft.ScrollMode.AUTO
        page.theme_mode = ft.ThemeMode.LIGHT

        # --- ЗМІННІ СТАНУ ---
        selected_image_paths = []
        
        # --- НАЛАШТУВАННЯ API КЛЮЧА ---
        api_key_input = ft.TextField(label="Вставте ваш Gemini API Key сюди", width=300, password=True, can_reveal_password=True)
        
        def save_api_key(e):
            save_api_key_to_file(api_key_input.value)
            settings_dialog.open = False
            page.snack_bar = ft.SnackBar(content=ft.Text("✅ Новий API Ключ успішно збережено!"), bgcolor=ft.colors.GREEN)
            page.snack_bar.open = True
            page.update()

        settings_dialog = ft.AlertDialog(
            title=ft.Text("Налаштування API"),
            content=ft.Column([
                ft.Text("Введіть ваш секретний ключ від Google Gemini:"),
                api_key_input
            ], tight=True),
            actions=[ft.TextButton("Зберегти", on_click=save_api_key)]
        )
        page.overlay.append(settings_dialog)

        def open_settings(e):
            saved_key = get_saved_api_key()
            if saved_key:
                api_key_input.value = saved_key
            else:
                api_key_input.value = DEFAULT_API_KEY
            settings_dialog.open = True
            page.update()

        # --- ЕЛЕМЕНТИ ІНТЕРФЕЙСУ ---
        title_row = ft.Row([
            ft.Text("VET-INSPECTOR PRO", size=20, weight=ft.FontWeight.BOLD, color=ft.colors.BLUE_900),
            ft.TextButton("⚙️", on_click=open_settings, tooltip="Налаштування API")
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        
        images_row = ft.Row(wrap=True, spacing=10)
        
        object_dropdown = ft.Dropdown(
            label="Об'єкт контролю",
            options=[
                ft.dropdown.Option("М'ясо (туші)"),
                ft.dropdown.Option("Молоко та молочні продукти"),
                ft.dropdown.Option("Риба жива"),
                ft.dropdown.Option("Інші харчові товари"),
                ft.dropdown.Option("Місце торгівлі/Обладнання"),
            ],
            width=350
        )
        
        temp_input = ft.TextField(label="T °C", width=100)
        inspector_comment = ft.TextField(label="Висновок інспектора", expand=True, hint_text="Коментар...")
        
        risk_indicator = ft.Container(
            content=ft.Text("РІВЕНЬ РИЗИКУ: НЕ ВИЗНАЧЕНО", color=ft.colors.WHITE, weight=ft.FontWeight.BOLD),
            bgcolor=ft.colors.GREY, padding=10, border_radius=5, width=350, alignment=ft.alignment.center
        )
        
        ai_response_text = ft.Markdown(value="*Очікування об'єкта...*", selectable=True, extension_set="gitHubWeb")

        # --- ФУНКЦІЇ КАМЕРИ ---
        def pick_file_result(e):
            if e.files:
                for f in e.files:
                    selected_image_paths.append(f.path)
                    images_row.controls.append(
                        ft.Image(src=f.path, width=100, height=100, fit=ft.ImageFit.COVER, border_radius=5)
                    )
                page.update()

        file_picker = ft.FilePicker()
        file_picker.on_result = pick_file_result
        page.overlay.append(file_picker)

        # --- ЛЕГКИЙ ЗАПИТ ДО ШІ ЧЕРЕЗ REQUESTS ---
        def perform_analysis(e):
            current_key = get_saved_api_key() or DEFAULT_API_KEY
            if not current_key.strip():
                ai_response_text.value = "❌ Будь ласка, вставте свій API-ключ у Налаштуваннях (⚙️ у правому верхньому куті)."
                page.update()
                return

            if "пиво будеш" in inspector_comment.value.lower():
                ai_response_text.value = "## БЕЗ РОМАНА ВАСИЛЬОВИЧА НІ ! 🍻"
                risk_indicator.bgcolor = ft.colors.BLUE
                risk_indicator.content.value = "РЕЖИМ ВІДПОЧИНКУ"
                page.update()
                return

            if not selected_image_paths:
                ai_response_text.value = "❌ Будь ласка, додайте хоча б одне фото для аналізу."
                page.update()
                return
                
            ai_response_text.value = "⏳ *Збираю дані та формую юридичне обґрунтування...*"
            page.update()

            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={current_key}"
                
                parts = []
                # Додаємо фотографії
                for path in selected_image_paths:
                    with open(path, "rb") as f:
                        b64_data = base64.b64encode(f.read()).decode("utf-8")
                        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": b64_data}})
                
                # Додаємо текстовий промпт
                prompt = f"""
                Проаналізуй усі надані фото в комплексі. 
                Дані від інспектора:
                - Об'єкт: {object_dropdown.value}
                - Температура: {temp_input.value} °C
                - ВИСНОВОК ІНСПЕКТОРА: {inspector_comment.value}
                
                Твоє завдання:
                1. Визнач рівень ризику тегом: [РИЗИК_ЗЕЛЕНИЙ], [РИЗИК_ЖОВТИЙ] або [РИЗИК_ЧЕРВОНИЙ].
                2. Опиши виявлені порушення (гігієна, чистота, ножі, рукавички тощо) з посиланням на пункти законодавства.
                3. Зазнач можливі штрафи та алгоритм дій.
                """
                parts.append({"text": prompt})
                
                # Формуємо JSON пакет із системними інструкціями
                payload = {
                    "system_instruction": {"parts": [{"text": system_instruction}]},
                    "contents": [{"parts": parts}]
                }
                
                resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"})
                
                if resp.status_code != 200:
                    ai_response_text.value = f"❌ Помилка API ({resp.status_code}): Можливо ключ недійсний або відсутній інтернет. Перевірте ключ у налаштуваннях."
                    page.update()
                    return
                    
                result_text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                
                # Обробка результатів та зміна кольору
                if "[РИЗИК_ЗЕЛЕНИЙ]" in result_text:
                    risk_indicator.bgcolor = ft.colors.GREEN
                    risk_indicator.content.value = "РІВЕНЬ РИЗИКУ: ЗЕЛЕНИЙ"
                elif "[РИЗИК_ЖОВТИЙ]" in result_text:
                    risk_indicator.bgcolor = ft.colors.YELLOW_800
                    risk_indicator.content.value = "РІВЕНЬ РИЗИКУ: ЖОВТИЙ"
                elif "[РИЗИК_ЧЕРВОНИЙ]" in result_text:
                    risk_indicator.bgcolor = ft.colors.RED
                    risk_indicator.content.value = "РІВЕНЬ РИЗИКУ: ЧЕРВОНИЙ"

                result_text = result_text.replace("[РИЗИК_ЗЕЛЕНИЙ]", "").replace("[РИЗИК_ЖОВТИЙ]", "").replace("[РИЗИК_ЧЕРВОНИЙ]", "")
                ai_response_text.value = result_text.strip()
                page.update()
                
            except Exception as ex:
                ai_response_text.value = f"❌ Помилка аналізу: {str(ex)}"
                page.update()

        def generate_act(e):
            if "Очікування" in ai_response_text.value or not ai_response_text.value:
                return
                
            current_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"AKT_{current_time}.html"
            filepath = os.path.join(REPORTS_DIR, filename)
            
            images_html = ""
            for path in selected_image_paths:
                with open(path, "rb") as img_file:
                    b64_str = base64.b64encode(img_file.read()).decode('utf-8')
                    images_html += f"<img src='data:image/jpeg;base64,{b64_str}' style='max-width: 300px; margin: 10px; border-radius: 5px; box-shadow: 2px 2px 5px grey;'><br>"

            html_content = f"""
            <html>
            <head>
                <meta charset='utf-8'>
                <title>Акт Обстеження</title>
                <style>
                    body {{ font-family: Arial, sans-serif; padding: 20px; max-width: 800px; margin: auto; }}
                    h1 {{ color: #0d47a1; text-align: center; border-bottom: 2px solid #0d47a1; padding-bottom: 10px; }}
                    .info-block {{ background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
                    .ai-text {{ white-space: pre-wrap; line-height: 1.6; }}
                    .photos {{ text-align: center; }}
                </style>
            </head>
            <body>
                <h1>АКТ ВЕТЕРИНАРНО-САНІТАРНОГО ОБСТЕЖЕННЯ</h1>
                <div class="info-block">
                    <p><strong>Дата:</strong> {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                    <p><strong>Об'єкт:</strong> {object_dropdown.value}</p>
                    <p><strong>Температура:</strong> {temp_input.value} °C</p>
                    <p><strong>Висновок інспектора:</strong> {inspector_comment.value}</p>
                    <p><strong>{risk_indicator.content.value}</strong></p>
                </div>
                
                <h2>Зафіксовані фотоматеріали:</h2>
                <div class="photos">
                    {images_html}
                </div>
                
                <h2>Юридичний висновок (ШІ PETROVET 49.0):</h2>
                <div class="ai-text">{ai_response_text.value}</div>
            </body>
            </html>
            """
            
            try:
                with open(filepath, "w", encoding="utf-8") as file:
                    file.write(html_content)
                ai_response_text.value += f"\n\n---\n**✅ АКТ ЗБЕРЕЖЕНО!**\nШукайте файл `{filename}` у папці Завантаження (Downloads)."
            except Exception as err:
                ai_response_text.value += f"\n\n---\n**❌ Помилка збереження акту:** {str(err)}"
            page.update()

        def reset_form(e):
            selected_image_paths.clear()
            images_row.controls.clear()
            temp_input.value = ""
            inspector_comment.value = ""
            object_dropdown.value = None
            ai_response_text.value = "*Очікування об'єкта...*"
            risk_indicator.bgcolor = ft.colors.GREY
            risk_indicator.content.value = "РІВЕНЬ РИЗИКУ: НЕ ВИЗНАЧЕНО"
            page.update()

        # --- КОМПОНУВАННЯ СТОРІНКИ ---
        page.add(
            ft.Column([
                title_row,
                ft.Row([
                    ft.ElevatedButton("📷 ДОДАТИ ФОТО", on_click=lambda _: file_picker.pick_files(allow_multiple=True)),
                    ft.ElevatedButton("🔄 НОВЕ ОБСТЕЖЕННЯ", on_click=reset_form, color=ft.colors.RED_700),
                ], alignment=ft.MainAxisAlignment.CENTER),
                images_row,
                object_dropdown,
                ft.Row([temp_input, inspector_comment], alignment=ft.MainAxisAlignment.CENTER),
                ft.ElevatedButton("🔍 ПРОВЕСТИ ОБСТЕЖЕННЯ", on_click=perform_analysis, width=350, bgcolor=ft.colors.BLUE_900, color=ft.colors.WHITE),
                risk_indicator,
                ft.Divider(),
                ai_response_text,
                ft.Divider(),
                ft.ElevatedButton("📄 СКЛАСТИ АКТ", on_click=generate_act, width=350, bgcolor=ft.colors.GREEN_700, color=ft.colors.WHITE)
            ], alignment=ft.MainAxisAlignment.START, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        )
        
    except Exception as e:
        page.clean()
        page.add(
            ft.Text("❌ КРИТИЧНА ПОМИЛКА:", color="red", size=22, weight="bold"),
            ft.Text(traceback.format_exc(), selectable=True, size=12)
        )

ft.app(target=main)