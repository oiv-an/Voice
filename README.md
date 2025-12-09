# VoiceCapture (Legacy 1.x)

> **⚠️ ВНИМАНИЕ: Эта версия (1.x) больше не поддерживается.**
>
> Актуальная версия **VoiceCapture 2.0** теперь является основной.
> Код версии 1.x доступен в ветке `legacy-1.x`.
>
> **[Перейти к актуальной версии (master)](https://github.com/oiv-an/Voice)**

---

# VoiceCapture

VoiceCapture — это мощная десктоп-утилита для Windows, предназначенная для быстрого голосового ввода и управления идеями. Она позволяет записывать голос с помощью глобальных горячих клавиш, распознавать речь с использованием передовых моделей (Groq, OpenAI, GigaAM) и автоматически вставлять текст в любое приложение.

---

## 🚀 Что нового в версии 1.2.0

### 🛡️ Crash Recovery (Восстановление при сбоях)
Теперь ваши записи в безопасности!
- **Автосохранение:** Аудио сохраняется на диск сразу после записи.
- **Восстановление:** Если приложение зависнет или закроется с ошибкой, при следующем запуске оно автоматически найдет и обработает потерянные записи.
- **Очистка:** Файлы удаляются только после успешного распознавания.

### ⚡ Ускорение аудио (x2)
- **Оптимизация:** Аудио автоматически ускоряется в 2 раза перед отправкой в нейросеть.
- **Экономия:** Это уменьшает размер передаваемых данных и ускоряет распознавание.

### ✨ Список идей (Idea List)
Теперь вы не потеряете ни одной мысли во время работы!
- **Новый режим записи:** Нажмите `Ctrl+Win+Alt` для записи "идеи".
- **Быстрая конвертация:** Нажмите `Alt` во время обычной записи, чтобы превратить её в идею.
- **Визуальный список:** Идеи отображаются в отдельном списке прямо в окне приложения.
- **Управление:**
  - Кликните по идее, чтобы зачеркнуть её (выполнено).
  - Зачеркнутые идеи автоматически удаляются через 5 секунд.
  - Кнопка "Очистить список" для быстрого удаления всех записей.
- **Логирование:** Все идеи (даже удаленные) сохраняются в файл `logs/ideas.log` с временными метками.

---

## 📋 Основные возможности

- **Глобальные горячие клавиши:** Запуск записи из любого приложения.
- **Мульти-бэкенд распознавание:**
  - **Groq:** Молниеносное распознавание через Whisper Large v3.
  - **OpenAI:** Высокая точность с моделями Whisper.
  - **Local (GigaAM-v3):** Локальное распознавание без отправки данных в интернет (для коротких фраз).
- **LLM-постпроцессинг:** Автоматическое исправление пунктуации, грамматики и форматирования с помощью GPT-4o, GPT-5.1 или моделей Groq.
- **Авто-вставка:** Распознанный текст автоматически копируется в буфер обмена и вставляется (Ctrl+V).
- **Умный каскад:** Автоматическое переключение на облачные сервисы, если локальная модель не справляется или запись слишком длинная.

---

## 🛠 Установка и запуск

### Требования
- Python 3.10+
- Windows 10/11

### Установка

1. Клонируйте репозиторий:
   ```bash
   git clone https://github.com/oiv-an/Voice.git
   cd Voice
   ```

2. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```

### Запуск

```bash
python src/main.py
```

При первом запуске в корне проекта будет создан файл `config.yaml` с настройками по умолчанию.

---

## ⚙️ Настройка

Все настройки доступны через графический интерфейс (иконка ⚙️) или напрямую в файле `config.yaml`.

### Пример `config.yaml`

```yaml
app:
  name: VoiceCapture
  version: 1.1.0

hotkeys:
  record: ctrl+win
  record_idea: ctrl+win+alt
  cancel: esc
  toggle_window: ctrl+alt+s
  toggle_debug: ctrl+alt+d

recognition:
  backend: groq        # groq / openai / local
  local:
    model: fixed
    device: cuda
    compute_type: float32
  openai:
    api_key: sk-...
    model: gpt-4o-transcribe
    model_process: gpt-5.1
    base_url: https://api.openai.com/v1
  groq:
    api_key: gsk-...
    model: whisper-large-v3
    model_process: moonshotai/kimi-k2-instruct

postprocess:
  enabled: true
  mode: llm            # simple / llm
  llm_backend: openai  # groq / openai
  groq:
    model: moonshotai/kimi-k2-instruct
  openai:
    model: gpt-5.1

# ... другие секции (audio, ui, logging)
```

---

## 📂 Структура проекта

- `src/main.py` — Точка входа.
- `src/config/` — Управление конфигурацией (`config.yaml`).
- `src/ui/` — Графический интерфейс (PyQt6).
- `src/audio/` — Запись звука.
- `src/recognition/` — Логика распознавания и постпроцессинга.
- `src/hotkey/` — Управление глобальными горячими клавишами.
- `logs/` — Логи приложения и транскрипций.

---

## 📝 История изменений (Changelog)

### [1.3.0] - 2025-12-09
#### Добавлено
- Возможность выбора аудиоустройства (микрофона) в настройках.

### [1.2.0] - 2025-12-07
#### Добавлено
- Система восстановления записей при сбоях (Crash Recovery).
- Автоматическое ускорение аудио (x2) для оптимизации распознавания.

### [1.1.0] - 2025-12-04
#### Добавлено
- Функция "Список идей": отдельный режим записи для быстрых заметок.
- Горячая клавиша `Ctrl+Win+Alt` для записи идей.
- Возможность конвертировать текущую запись в идею нажатием `Alt`.
- UI-компонент для отображения и управления списком идей.
- Логирование всех идей в `logs/ideas.log`.
- Обновлен дизайн списка идей для соответствия общему стилю.

### [1.0.0] - 2025-12-01
#### Добавлено
- Базовый функционал записи и распознавания.
- Поддержка Groq, OpenAI и GigaAM (Local).
- LLM-постпроцессинг.
- Плавающее окно и иконка в трее.
- Единый файл конфигурации `config.yaml`.

---

## 👨‍💻 Разработка

Проект создан с использованием подхода "Вайб-кодинг".
Архитектура разработана с помощью Claude 4.5 OPUS / GPT-5.1 / Gemini 3 pro.
Код написан и поддерживается с любовью к Python и чистому коду.

---

**VoiceCapture** — говорите, а не печатайте.

---
---

# VoiceCapture (EN)

VoiceCapture is a powerful desktop utility for Windows designed for quick voice input and idea management. It allows you to record your voice using global hotkeys, recognize speech with advanced models (Groq, OpenAI, GigaAM), and automatically paste the text into any application.

---

## 🚀 What's New in Version 1.2.0

### 🛡️ Crash Recovery
Your recordings are now safe!
- **Auto-save:** Audio is saved to disk immediately after recording.
- **Recovery:** If the app hangs or crashes, it will automatically find and process lost recordings on the next startup.
- **Cleanup:** Files are deleted only after successful recognition.

### ⚡ Audio Speedup (x2)
- **Optimization:** Audio is automatically sped up by 2x before being sent to the neural network.
- **Efficiency:** This reduces data size and speeds up recognition.

### 🎤 Microphone Selection
- **Settings:** You can now select a specific input device (microphone) in the app settings.
- **Convenience:** Useful if you have multiple microphones or want to use a non-default system device.

### ✨ Idea List
Never lose a thought while you're working!
- **New Recording Mode:** Press `Ctrl+Win+Alt` to record an "idea."
- **Quick Conversion:** Press `Alt` during a regular recording to turn it into an idea.
- **Visual List:** Ideas are displayed in a separate list directly in the application window.
- **Management:**
  - Click on an idea to strike it through (mark as done).
  - Struck-through ideas are automatically deleted after 5 seconds.
  - A "Clear List" button to quickly remove all entries.
- **Logging:** All ideas (even deleted ones) are saved to `logs/ideas.log` with timestamps.

---

## 📋 Key Features

- **Global Hotkeys:** Start recording from any application.
- **Multi-Backend Recognition:**
  - **Groq:** Lightning-fast recognition via Whisper Large v3.
  - **OpenAI:** High accuracy with Whisper models.
  - **Local (GigaAM-v3):** Local recognition without sending data to the internet (for short phrases).
- **LLM Post-processing:** Automatic correction of punctuation, grammar, and formatting using GPT-4o, GPT-5.1, or Groq models.
- **Auto-Paste:** Recognized text is automatically copied to the clipboard and pasted (Ctrl+V).
- **Smart Cascade:** Automatically switches to cloud services if the local model fails or the recording is too long.

---

## 🛠 Installation and Usage

### Requirements
- Python 3.10+
- Windows 10/11

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/oiv-an/Voice.git
   cd Voice
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Running the App

```bash
python src/main.py
```

On the first run, a `config.yaml` file with default settings will be created in the project root.

---

## ⚙️ Configuration

All settings are available through the GUI (⚙️ icon) or directly in the `config.yaml` file.

### Example `config.yaml`

```yaml
app:
  name: VoiceCapture
  version: 1.1.0

hotkeys:
  record: ctrl+win
  record_idea: ctrl+win+alt
  cancel: esc
  toggle_window: ctrl+alt+s
  toggle_debug: ctrl+alt+d

recognition:
  backend: groq        # groq / openai / local
  local:
    model: fixed
    device: cuda
    compute_type: float32
  openai:
    api_key: sk-...
    model: gpt-4o-transcribe
    model_process: gpt-5.1
    base_url: https://api.openai.com/v1
  groq:
    api_key: gsk-...
    model: whisper-large-v3
    model_process: moonshotai/kimi-k2-instruct

postprocess:
  enabled: true
  mode: llm            # simple / llm
  llm_backend: openai  # groq / openai
  groq:
    model: moonshotai/kimi-k2-instruct
  openai:
    model: gpt-5.1

# ... other sections (audio, ui, logging)
```

---

## 📂 Project Structure

- `src/main.py` — Entry point.
- `src/config/` — Configuration management (`config.yaml`).
- `src/ui/` — Graphical user interface (PyQt6).
- `src/audio/` — Audio recording.
- `src/recognition/` — Recognition and post-processing logic.
- `src/hotkey/` — Global hotkey management.
- `logs/` — Application and transcription logs.

---

## 📝 Changelog

### [1.3.0] - 2025-12-09
#### Added
- Ability to select audio input device (microphone) in settings.

### [1.2.0] - 2025-12-07
#### Added
- Crash Recovery system.
- Automatic audio speedup (x2) for optimized recognition.

### [1.1.0] - 2025-12-04
#### Added
- "Idea List" feature: a separate recording mode for quick notes.
- `Ctrl+Win+Alt` hotkey for recording ideas.
- Ability to convert a current recording to an idea by pressing `Alt`.
- UI component for displaying and managing the idea list.
- Logging of all ideas to `logs/ideas.log`.
- Updated the design of the idea list to match the overall style.

### [1.0.0] - 2025-12-01
#### Added
- Basic recording and recognition functionality.
- Support for Groq, OpenAI, and GigaAM (Local).
- LLM post-processing.
- Floating window and tray icon.
- Unified `config.yaml` configuration file.

---

## 👨‍💻 Development

This project was created using the "Vibe-Coding" approach.
The architecture was designed with the help of Claude 4.5 OPUS / GPT-5.1 / Gemini 3 pro.
The code is written and maintained with a love for Python and clean code.

---

**VoiceCapture** — Speak, don't type.
