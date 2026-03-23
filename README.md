# VoiceCapture 2.3.0

**VoiceCapture** — портативная open-source утилита для голосового ввода на Windows. Записывает речь, транскрибирует через облачные API (Groq, OpenAI Whisper), улучшает текст через LLM и автоматически вставляет результат в активное поле. Поддерживает интеграцию с n8n Webhook для автоматизации обработки голосовых заметок.

> ⭐ Проект открытый. Fork, Star, PR приветствуются.

---

## 🚀 Быстрый старт

1. Скачайте `VoiceCapture.exe` из раздела [Releases](https://github.com/oiv-an/Voice/releases).
2. Запустите файл — установка не требуется.
3. Откройте настройки (⚙️) и введите API-ключ Groq или OpenAI.
4. Зажмите `Ctrl + Win` — говорите — отпустите. Текст вставится сам.

---

## ✨ Возможности

| Функция                 | Описание                                                          |
| ----------------------- | ----------------------------------------------------------------- |
| 🎙️ **Голосовой ввод**    | Нажми `Ctrl+Win`, говори, отпусти — текст появится в нужном месте |
| 💡 **Голосовые заметки** | `Ctrl+Win+Alt` — запись идеи/заметки отдельным потоком            |
| 🤖 **LLM-постобработка** | Автоисправление пунктуации, грамматики через Groq/OpenAI          |
| 🔗 **N8N Webhook**       | Заметки автоматически улетают на ваш N8N workflow                 |
| 📋 **Clipboard**         | Распознанный текст сразу в буфер + автовставка                    |
| 📜 **История**           | Последние 50 записей с raw/processed вариантами                   |
| 🔄 **Crash Recovery**    | Аудио сохраняется и переобрабатывается после сбоя                 |
| ⚡ **Ускорение x2**      | Опциональное ускорение аудио для экономии API-трафика             |
| 🎛️ **Выбор микрофона**   | Любое аудиоустройство в настройках                                |
| 🪟 **Портативность**     | Один `.exe`, без инсталляции, без прав администратора             |

---

## ⌨️ Горячие клавиши

| Клавиши                       | Действие                                                                    |
| ----------------------------- | --------------------------------------------------------------------------- |
| `Ctrl + Win` (удержать)       | Начать запись речи → отпустить = транскрибировать и вставить                |
| `Ctrl + Win + Alt` (удержать) | Записать голосовую заметку (идею) → отправить на N8N или сохранить в список |
| `Esc`                         | Отменить текущую запись                                                     |
| `Ctrl + Alt + S`              | Показать/скрыть главное окно                                                |

> Все горячие клавиши настраиваемые — меняются в разделе «Горячие клавиши» в настройках.

---

## 🔗 Интеграция с N8N Webhook

Самая мощная фича для автоматизации. Когда вы нажимаете `Ctrl+Win+Alt` и диктуете заметку:

1. Речь транскрибируется и обрабатывается LLM.
2. Результат отправляется POST-запросом на указанный N8N Webhook URL.
3. N8N может записать в Notion, отправить в Telegram, создать задачу в Jira — что угодно.

### Настройка:

1. В N8N создайте Workflow с триггером **Webhook**.
2. Скопируйте URL вида `https://your-n8n.example.com/webhook/abc123`.
3. В VoiceCapture откройте ⚙️ Настройки → раздел **«Интеграции»**.
4. Вставьте URL в поле **«Webhook N8N (конечная точка)»**.
5. Сохраните.

### Что приходит на Webhook:

```json
{
  "text": "Текст распознанной и обработанной заметки",
  "timestamp": "2026-03-15T10:30:00.000000",
  "source": "VoiceCapture"
}
```

### Поведение при заполненном Webhook:

- Список идей в главном окне **скрывается** — всё уходит на сервер.
- При записи статус показывает **«Запись → N8N Webhook...»**.
- После отправки появляется ✅ **«Отправлено на N8N Webhook»** или ❌ при ошибке (5 сек).
- При пустом поле Webhook — обычный режим: список идей в окне + `logs/ideas.log`.

---

## ⚙️ Настройка

### Получение бесплатного Groq API ключа

Groq — самый быстрый вариант с щедрым бесплатным планом:

1. Зайдите на [console.groq.com](https://console.groq.com).
2. Зарегистрируйтесь / войдите.
3. В разделе **«API Keys»** создайте новый ключ.
4. Вставьте в VoiceCapture: ⚙️ → **Groq API key**.

### Описание всех настроек

| Раздел                   | Параметр         | Описание                                                               |
| ------------------------ | ---------------- | ---------------------------------------------------------------------- |
| **Аудио**                | Микрофон         | Выбор устройства ввода                                                 |
| **Аудио**                | Ускорение x2     | Ускоряет аудио перед отправкой (меньше трафика)                        |
| **Сервис распознавания** | Backend          | Groq или OpenAI                                                        |
| **Сервис распознавания** | API Key          | Ключ выбранного провайдера                                             |
| **Сервис распознавания** | OpenAI Base URL  | Custom endpoint (совместимые API: LM Studio, vLLM)                     |
| **Горячие клавиши**      | Запись           | По умолчанию `ctrl+win`                                                |
| **Горячие клавиши**      | Запись идеи      | По умолчанию `ctrl+win+alt`                                            |
| **Модели ASR**           | Groq ASR model   | По умолчанию `whisper-large-v3`                                        |
| **Модели ASR**           | OpenAI ASR model | По умолчанию `whisper-1`                                               |
| **Постобработка**        | Включить         | Вкл/выкл LLM-коррекции                                                 |
| **Постобработка**        | Сервис           | Groq или OpenAI для LLM                                                |
| **Постобработка**        | Модели           | LLM-модели для коррекции                                               |
| **Постобработка**        | System Prompt    | Инструкция для LLM (можно попросить переводить, писать в стиле и т.д.) |
| **Интеграции**           | Webhook N8N      | URL конечной точки N8N для голосовых заметок                           |

---

## 🏗️ Архитектура

```
voice2.0/
├── src/
│   ├── main.py                  # App класс, оркестратор
│   ├── config/
│   │   └── settings.py          # Датаклассы настроек, load/save YAML
│   ├── audio/
│   │   └── recorder.py          # Запись через sounddevice
│   ├── hotkey/
│   │   └── hotkey_manager.py    # Глобальные хоткеи через keyboard
│   ├── recognition/
│   │   ├── groq_api.py          # Groq Whisper транскрибация
│   │   ├── openai_api.py        # OpenAI Whisper транскрибация
│   │   └── postprocessor.py     # LLM постобработка текста
│   ├── clipboard/
│   │   └── clipboard_manager.py # Копирование и вставка
│   ├── ui/
│   │   ├── floating_window.py   # Главное плавающее окно
│   │   ├── settings_dialog.py   # Диалог настроек
│   │   ├── history_dialog.py    # Окно истории
│   │   └── system_tray.py       # Системный трей
│   └── utils/
│       ├── history.py           # История распознаваний
│       ├── recovery.py          # Восстановление после сбоя
│       └── logger.py            # Настройка loguru
├── config.yaml                  # Конфиг (создаётся автоматически, в .gitignore)
├── build_exe.py                 # Сборка в .exe через PyInstaller
└── requirements.txt
```

### Ключевые решения:

- **Один файл конфига** — `config.yaml` в корне проекта/рядом с `.exe`. Нет `config.local.yaml`, нет нескольких файлов.
- **Каскад backend'ов** — если Groq недоступен, автоматически пробует OpenAI (и наоборот), до 5 попыток.
- **Webhook в daemon-потоке** — отправка на N8N не блокирует UI и основную обработку.
- **Безопасные сигналы Qt** — все обращения к UI из воркер-потоков через `pyqtSignal`.
- **PyInstaller onefile** — все зависимости упакованы в один `.exe`, включая SSL-сертификаты (certifi).

---

## 🛠️ Сборка из исходников

Требования: **Python 3.12+**, Windows 10/11.

```bash
# Клонируем репозиторий
git clone https://github.com/oiv-an/Voice.git
cd voice2.0

# Устанавливаем зависимости
pip install -r requirements.txt

# Запуск в dev-режиме
python src/main.py

# Сборка в .exe
python build_exe.py
# Готовый файл: dist/VoiceCapture.exe
```

### Зависимости (requirements.txt)

| Пакет                   | Назначение                      |
| ----------------------- | ------------------------------- |
| `PyQt6`                 | GUI                             |
| `sounddevice` + `numpy` | Запись аудио                    |
| `keyboard`              | Глобальные хоткеи               |
| `groq` + `openai`       | API клиенты                     |
| `loguru`                | Логирование                     |
| `pyyaml`                | Конфиг                          |
| `pyperclip`             | Clipboard                       |
| `certifi`               | SSL-сертификаты для PyInstaller |

---

## 📋 Changelog

### v2.3.0 (текущая)

- **🔗 N8N Webhook интеграция:** В настройках (раздел «Интеграции») можно указать URL Webhook N8N. При нажатии `Ctrl+Win+Alt` голосовая заметка транскрибируется и автоматически отправляется POST-запросом на указанный URL.
- **🔄 Webhook mode:** Если Webhook заполнен — список идей в главном окне скрывается, результат идёт только на сервер. Показывается статус ✅/❌.
- **📍 Статус записи:** При записи идеи/Webhook показывается «Запись → N8N Webhook...» или «Запись идеи...» вместо обычного «Запись...».
- **🐛 Исправлено мигание** при нажатии `Ctrl+Win+Alt` — надпись больше не мигает при добавлении Alt к зажатым Ctrl+Win. Фикс в `hotkey_manager.py`: `_handle_release()` теперь проверяет, что Ctrl+Win действительно отпущены, прежде чем останавливать запись.

### v2.2.7
- **Исправлена ошибка SSL:** Исправлена проблема с SSL-сертификатами при работе собранного exe-файла.

### v2.2.6
- **Улучшение интерфейса:** Если отключен постпроцессинг (LLM), второе текстовое поле скрывается.

### v2.2.5
- **Обслуживание:** Кнопка очистки папки RECOVERY в настройках.
- **Баг-фикс:** Пустые аудиофайлы больше не накапливаются.

### v2.2.4
- **Сохранение размера окна:** Размер запоминается между сессиями.

### v2.2.3
- **Фильтрация галлюцинаций LLM:** Фразы-заглушки («Продолжение следует...») игнорируются.

### v2.2.2
- **Пустой ввод:** Если распознавание вернуло пустой текст — показывается заглушка.

### v2.2.1
- **Исправление зависаний:** Устранена критическая ошибка зависания при быстрых хоткеях.

### v2.2.0
- **История распознаваний:** Кнопка 🕒 — последние 50 записей с копированием.

### v2.1.2
- **Изменение размера окна:** Уголок resize в правом нижнем углу.

### v2.1.1
- **Настраиваемый System Prompt:** Поле для редактирования инструкции LLM в настройках.

### v2.1.0
- Поддержка Groq API.

---

## 🤝 Contributing

Pull requests приветствуются. Для крупных изменений — сначала откройте Issue для обсуждения.

1. Fork репозитория.
2. Создайте feature-ветку: `git checkout -b feature/my-feature`.
3. Commit: `git commit -m 'Add my feature'`.
4. Push: `git push origin feature/my-feature`.
5. Откройте Pull Request.

---

## 📄 Лицензия

MIT License. Делайте что хотите.

---

# VoiceCapture 2.3.0 (English)

**VoiceCapture** is a portable open-source voice typing utility for Windows. Records speech, transcribes via cloud APIs (Groq, OpenAI Whisper), improves text via LLM, and automatically pastes the result into the active field. Supports n8n Webhook integration for automating voice note processing.

## Features

- 🎙️ **Voice Input:** Hold `Ctrl+Win`, speak, release — text appears where you need it.
- 💡 **Voice Notes:** `Ctrl+Win+Alt` — records an idea/note in a separate flow.
- 🤖 **LLM Post-processing:** Auto-corrects punctuation, grammar via Groq/OpenAI.
- 🔗 **N8N Webhook:** Notes automatically fly to your N8N workflow.
- 📋 **Clipboard:** Recognized text goes straight to clipboard + auto-paste.
- 📜 **History:** Last 50 recordings with raw/processed variants.
- 🔄 **Crash Recovery:** Audio is saved and reprocessed after a crash.
- ⚡ **x2 Speedup:** Optional audio speedup to save API traffic.
- 🎛️ **Microphone Selection:** Any audio device in settings.
- 🪟 **Portable:** Single `.exe`, no installation, no admin rights required.

## N8N Webhook Integration

When you press `Ctrl+Win+Alt` and dictate a note:

1. Speech is transcribed and processed by LLM.
2. Result is sent as a POST request to the specified N8N Webhook URL.
3. N8N can write to Notion, send to Telegram, create a task in Jira — anything.

**Payload sent to Webhook:**
```json
{
  "text": "Transcribed and processed note text",
  "timestamp": "2026-03-15T10:30:00.000000",
  "source": "VoiceCapture"
}
```

**Setup:** Settings (⚙️) → **Integrations** → **N8N Webhook (endpoint)** → paste your webhook URL.

## Changelog

### v2.3.0
- **N8N Webhook integration:** Voice notes are automatically sent to N8N webhook URL (configurable in Settings → Integrations).
- **Webhook mode:** When webhook is set, the ideas list is hidden; results go to server only. Shows ✅/❌ status.
- **Recording status:** Shows "Recording → N8N Webhook..." or "Recording idea..." instead of generic "Recording...".
- **Fixed flickering** when pressing `Ctrl+Win+Alt` — status label no longer flickers when adding Alt to held Ctrl+Win.

### v2.2.7
- SSL certificate fix for built exe file.

### v2.2.6
- UI: second text field hidden when post-processing is disabled.

### v2.2.5
- Added "Clear RECOVERY folder" button in settings.
- Fixed empty audio files accumulation.

### v2.2.4
- Window size is now saved between sessions.

### v2.2.3
- LLM hallucination filtering (placeholder phrases are ignored).

### v2.2.2
- Empty input placeholder.

### v2.2.1
- Fixed critical freeze bug on rapid hotkey presses.

### v2.2.0
- Recognition history with 🕒 button.

### v2.1.2
- Window resizing via bottom-right corner grip.

### v2.1.1
- Configurable LLM system prompt in settings.

### v2.1.0
- Groq API support added.

## Build from Source

Requirements: **Python 3.12+**, Windows 10/11.

```bash
git clone https://github.com/oiv-an/Voice.git
cd voice2.0
pip install -r requirements.txt

# Run in dev mode
python src/main.py

# Build .exe
python build_exe.py
# Output: dist/VoiceCapture.exe
```

## License

MIT License.
