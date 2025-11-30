# VoiceCapture

VoiceCapture — это небольшая утилита для Windows, которая позволяет диктовать текст в любое приложение с помощью глобальной горячей клавиши. Приложение записывает звук, отправляет его в сервис распознавания речи (Groq, OpenAI или локальная модель), при необходимости дополнительно обрабатывает текст через LLM, копирует результат в буфер обмена и вставляет его в активное окно.

Проект написан на Python с использованием PySide6 для интерфейса и спроектирован так, чтобы его можно было безопасно публиковать на GitHub без утечки API‑ключей.

---

## Возможности

- Глобальная горячая клавиша для старта/остановки записи (по умолчанию: `Ctrl + Win`)
- Плавающее окно, всегда поверх других, с компактным режимом
- Иконка в системном трее с быстрыми действиями
- Несколько бэкендов распознавания:
  - Groq Whisper API
  - OpenAI Whisper API (или любой OpenAI‑совместимый endpoint)
  - Локальный ASR‑бэкенд (сейчас GigaAM; Whisper через `faster-whisper` планируется)
- Постобработка текста:
  - Регулярная очистка (regex cleanup)
  - Опциональная LLM‑коррекция через Groq / OpenAI
- Интеграция с буфером обмена:
  - Копирование распознанного текста
  - Эмуляция `Ctrl+V` в активное окно с ретраями
- Настраиваемые горячие клавиши и модели через диалог настроек
- Логи с ротацией для отладки и истории транскриптов

---

## Установка и запуск (быстрый старт)

### Требования

- Windows 11
- Python 3.11+ (рекомендуется 64‑бит)
- Микрофон, доступный в системе

### 1. Клонирование репозитория

```bash
git clone https://github.com/oiv-an/Voice.git
cd Voice
```

### 2. Создание и активация виртуального окружения

```bash
python -m venv .venv
.venv\Scripts\activate
```

Если используете PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 4. Настройка ключей (минимально необходимое)

Создайте локальный конфиг (игнорируется git):

```text
src/config/config.local.yaml
```

Минимальный пример для Groq:

```yaml
recognition:
  backend: groq

  groq:
    api_key: gsk_YOUR_KEY
    model: whisper-large-v3
    model_process: mixtral-8x7b-32768

postprocess:
  llm_backend: groq
```

Или для OpenAI:

```yaml
recognition:
  backend: openai

  openai:
    api_key: sk_YOUR_KEY
    model: whisper-1
    model_process: gpt-4o-mini
    base_url: https://api.openai.com/v1

postprocess:
  llm_backend: openai
```

> Важно: `config.local.yaml` не коммитится и используется только локально. Базовый [`config.yaml`](src/config/config.yaml:1) остаётся обезличенным.

### 5. Запуск приложения

Из корня проекта:

```bash
.venv\Scripts\activate
python src/main.py
```

После запуска:

- В системном трее появится иконка приложения.
- Плавающее окно будет отображаться поверх других окон.

Горячие клавиши по умолчанию:

- `Ctrl + Win` — зажать для записи, отпустить для остановки.
- `Esc` — отмена записи.
- `Ctrl + Alt + S` — показать/скрыть окно.
- `Ctrl + Alt + D` — переключить debug‑режим (частично реализован).

Рабочий сценарий:

1. Сфокусируйте любое текстовое поле (редактор, браузер, мессенджер и т.п.).
2. Зажмите `Ctrl + Win` и продиктуйте текст.
3. Отпустите клавиши.
4. Приложение:
   - Запишет аудио.
   - Отправит его в выбранный бэкенд распознавания.
   - При необходимости прогонит текст через LLM‑постобработку.
   - Скопирует итоговый текст в буфер обмена.
   - Эмулирует `Ctrl+V` в активное окно.

---

## Обзор архитектуры

Высокоуровневые компоненты:

- Основное приложение:
  - [`src/main.py`](src/main.py)
  - [`App`](src/main.py:34) оркестрирует запись, распознавание, постобработку, буфер обмена, UI и горячие клавиши.
- Конфигурация:
  - [`AppSettings`](src/config/settings.py:121) загружает YAML‑конфиг в типизированные dataclass’ы.
  - [`src/config/config.yaml`](src/config/config.yaml) — дефолтный, **обезличенный** конфиг (без реальных ключей).
- Аудио:
  - [`AudioRecorder`](src/audio/recorder.py:21) пишет звук с дефолтного входного устройства через `sounddevice`.
- Бэкенды распознавания:
  - [`create_recognizer`](src/recogniction/__init__.py:1) — фабрика, выбирает бэкенд.
  - [`GroqWhisperRecognizer`](src/recognition/groq_api.py:19) — Groq Whisper API.
  - [`OpenAIWhisperRecognizer`](src/recognition/openai_api.py:19) — OpenAI / OpenAI‑совместимый API.
  - [`GigaAMRecognizer`](src/recognition/gigaam_local.py:12) — локальная ASR‑модель (GigaAM).
- Постобработка:
  - [`TextPostprocessor`](src/recognition/postprocessor.py:1) — regex‑очистка + опциональная LLM‑коррекция.
- Буфер обмена:
  - [`ClipboardManager`](src/clipboard/clipboard_manager.py:1) — копирование и вставка с ретраями.
- UI:
  - [`FloatingWindow`](src/ui/floating_window.py:33) — основное плавающее окно.
  - [`SystemTrayIcon`](src/ui/system_tray.py:1) — иконка и меню в трее.
  - [`SettingsDialog`](src/ui/settings_dialog.py:1) — диалог настроек.
- Горячие клавиши:
  - [`HotKeyManager`](src/hotkey/hotkey_manager.py:1) — глобальные хоткеи через `pynput`.
- Логирование:
  - [`setup_logging`](src/utils/logger.py:1) — логирование на базе `loguru` с ротацией.

Более детальное описание модулей приведено в [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md:1).

---

## Безопасность и конфигурация API‑ключей

### Что уже реализовано

- Конфиг разделён на:
  - `recognition.openai` (`OpenAIRecognitionConfig`)
  - `recognition.groq` (`GroqRecognitionConfig`)
- Ключи для LLM‑постобработки **переиспользуются** из блока распознавания:
  - В [`App.__init__`](src/main.py:41) `post_cfg.groq.api_key` и `post_cfg.openai.api_key` заполняются из `recognition.groq.api_key` и `recognition.openai.api_key`.
- `.gitignore` защищает локальные конфиги и `.env`:
  - Игнорируются:
    - `.env`, `.env.*`, `*.env`
    - `config.local.yaml`, `config.local.yml`, `config.local.json`
    - `*.local.yaml`, `*.local.yml`, `*.local.json`
  - В `.gitignore` есть явный комментарий:
    - Не коммитить реальные ключи в дефолтный конфиг; держать `src/config/config.yaml` обезличенным.
- [`src/config/config.yaml`](src/config/config.yaml:1) очищен:
  - Реальные ключи удалены и заменены на заглушки:

    ```yaml
    recognition:
      backend: groq  # local, openai, groq
      local:
        model: large-v3
        device: cuda
        compute_type: float16
        language: ru
        beam_size: 5
        temperature: 0.0
      openai:
        api_key: sk-...        # ЗАПОЛНИТЬ ЛОКАЛЬНО в config.local.yaml или через UI
        model: whisper-1
        model_process: gpt-4
        language: ru
        base_url: https://api.openai.com/v1
      groq:
        api_key: gsk-...       # ЗАПОЛНИТЬ ЛОКАЛЬНО в config.local.yaml или через UI
        model: whisper-large-v3
        model_process: mixtral-8x7b-32768
        language: ru
    ```

Это означает, что `config.yaml` безопасен для публикации в публичном репозитории.

### Рекомендуемый workflow с git и секретами

1. **Никогда не хранить реальные API‑ключи в `src/config/config.yaml`.**
2. Для своих ключей использовать один из вариантов:
   - `src/config/config.local.yaml` (предпочтительно; игнорируется git).
   - Вводить ключи через UI (диалог настроек); перед коммитом убедиться, что в `config.yaml` не осталось реальных значений.
3. Рекомендуемый локальный конфиг: `config.local.yaml`.

Пример `src/config/config.local.yaml` (НЕ коммитить):

```yaml
recognition:
  openai:
    api_key: sk-YOUR_KEY
    model: whisper-1
    model_process: gpt-4o-mini
    base_url: https://api.openai.com/v1

  groq:
    api_key: gsk_YOUR_KEY
    model: whisper-large-v3
    model_process: mixtral-8x7b-32768

postprocess:
  llm_backend: groq
```

Фактически реализовано:

- [`AppSettings.load_default()`](src/config/settings.py:132) уже:
  - Загружает `config.yaml`.
  - Если есть, загружает `config.local.yaml`.
  - Делает глубокий merge: `config.local.yaml` перекрывает значения из `config.yaml`.

### Опционально: поддержка `.env`

Пока не реализовано, но кодовая база готова к добавлению `python-dotenv` и чтению ключей из переменных окружения:

- `GROQ_API_KEY`
- `OPENAI_API_KEY`

Это может быть дополнительным способом управления секретами.

---

## Git и безопасность: чеклист

Чтобы репозиторий оставался чистым и без секретов:

1. Инициализация git (если ещё не сделано):

   ```bash
   git init
   git add .
   git commit -m "Initial VoiceCapture MVP"
   ```

2. Перед пушем на GitHub:

   - Убедитесь, что в `src/config/config.yaml` **нет реальных ключей**.
   - Убедитесь, что локальные конфиги не попали в индекс:

     ```bash
     git status
     git restore --staged src/config/config.local.yaml  # если вдруг добавили
     ```

3. Добавление remote и пуш:

   ```bash
   git remote add origin git@github.com:YOUR_USER/VoiceCapture.git
   git push -u origin main
   ```

---

## Roadmap / чего не хватает до полного ТЗ

Текущий MVP реализует основной workflow, но некоторые пункты из исходного ТЗ ещё в планах:

- Конфиг и секреты:
  - [x] Merge `config.local.yaml` поверх `config.yaml` в [`AppSettings.load_default()`](src/config/settings.py:132).
  - [ ] Опциональная поддержка `.env` через `python-dotenv`.
- Локальный Whisper:
  - [ ] Добавить [`whisper_local.py`](src/recognition/whisper_local.py:1) на базе `faster-whisper`.
  - [ ] Дать выбор между GigaAM и Whisper в конфиге/UI.
  - [ ] Добавить [`gpu_check.py`](src/utils/gpu_check.py:1) для проверки CUDA / информации о GPU.
- Аудио / VAD:
  - [ ] Добавить [`vad.py`](src/audio/vad.py:1) с простой VAD (RMS/энергия).
  - [ ] Авто‑остановка записи по тишине > 1.5 сек.
- UI / UX:
  - [ ] Уточнить поведение трея (закрытие в трей vs полный выход).
  - [ ] Добавить звуки для start/stop/error (например, `assets/sounds/*.wav`).
- Debug:
  - [ ] Реализовать полноценный debug‑режим в [`App.toggle_debug_mode`](src/main.py:332) (переключение уровня логов, опциональная панель).
- Тесты:
  - [ ] Unit‑тесты для рекордера, локального распознавателя, буфера обмена, конфига.
  - [ ] Интеграционные тесты end‑to‑end.

---

## Заметки по разработке

- Логирование:
  - [`setup_logging`](src/utils/logger.py:1) настраивает `loguru` с ротацией.
  - Транскрипты дополнительно пишутся в `logs/transcripts.log` с ротацией по размеру.
- Ручной тест LLM:
  - [`tests/manual_llm_test.py`](tests/manual_llm_test.py:1) можно использовать для ручной проверки LLM‑постобработки с вашими ключами.

---

## Лицензия

Добавьте сюда предпочитаемую лицензию (например, MIT, Apache‑2.0). Пока лицензия не указана, проект де‑факто “all rights reserved”.

---

# VoiceCapture

VoiceCapture is a small desktop utility for Windows that lets you dictate text into any application using a global hotkey. It records audio, sends it to a speech‑to‑text backend (Groq, OpenAI, or local model), optionally post‑processes the text with an LLM, copies the result to the clipboard, and pastes it into the active window.

The project is written in Python with PySide6 for the UI and is designed to be safe to publish on GitHub without leaking API keys.

---

## Features

- Global hotkey to start/stop recording (default: `Ctrl + Win`)
- Floating always‑on‑top window with compact mode
- System tray icon with quick actions
- Multiple recognition backends:
  - Groq Whisper API
  - OpenAI Whisper API (or any OpenAI‑compatible endpoint)
  - Local ASR backend (currently GigaAM; Whisper via `faster-whisper` planned)
- Text post‑processing:
  - Regex cleanup
  - Optional LLM correction via Groq / OpenAI
- Clipboard integration:
  - Copies recognized text
  - Simulates `Ctrl+V` into the active window with retries
- Configurable hotkeys and models via settings dialog
- Log files with rotation for debugging and transcript history

---

## Architecture Overview

High‑level components:

- Core application:
  - [`src/main.py`](src/main.py)
  - [`App`](src/main.py:34) orchestrates recording, recognition, post‑processing, clipboard, UI, and hotkeys.
- Configuration:
  - [`AppSettings`](src/config/settings.py:121) loads YAML config into typed dataclasses.
  - [`src/config/config.yaml`](src/config/config.yaml) is the default, **generic** config (no real keys).
- Audio:
  - [`AudioRecorder`](src/audio/recorder.py:21) records audio from the default input device using `sounddevice`.
- Recognition backends:
  - [`create_recognizer`](src/recogniction/__init__.py:1) (factory, chooses backend).
  - [`GroqWhisperRecognizer`](src/recognition/groq_api.py:19) — Groq Whisper API.
  - [`OpenAIWhisperRecognizer`](src/recognition/openai_api.py:19) — OpenAI / OpenAI‑compatible API.
  - [`GigaAMRecognizer`](src/recognition/gigaam_local.py:12) — local ASR model (GigaAM).
- Post‑processing:
  - [`TextPostprocessor`](src/recognition/postprocessor.py:1) — regex cleanup + optional LLM correction.
- Clipboard:
  - [`ClipboardManager`](src/clipboard/clipboard_manager.py:1) — copy & paste with retries.
- UI:
  - [`FloatingWindow`](src/ui/floating_window.py:33) — main always‑on‑top window.
  - [`SystemTrayIcon`](src/ui/system_tray.py:1) — tray icon and menu.
  - [`SettingsDialog`](src/ui/settings_dialog.py:1) — configuration dialog.
- Hotkeys:
  - [`HotKeyManager`](src/hotkey/hotkey_manager.py:1) — global hotkeys via `pynput`.
- Logging:
  - [`setup_logging`](src/utils/logger.py:1) — loguru‑based logging with rotation.

A more detailed module‑level description is planned for [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## Security and Configuration of API Keys

### What is already implemented

- Config is split into:
  - `recognition.openai` (`OpenAIRecognitionConfig`)
  - `recognition.groq` (`GroqRecognitionConfig`)
- Post‑processing LLM keys are **reused** from recognition:
  - In [`App.__init__`](src/main.py:41), `post_cfg.groq.api_key` and `post_cfg.openai.api_key` are filled from `recognition.groq.api_key` and `recognition.openai.api_key`.
- `.gitignore` protects local configs and `.env` files:
  - Ignored:
    - `.env`, `.env.*`, `*.env`
    - `config.local.yaml`, `config.local.yml`, `config.local.json`
    - `*.local.yaml`, `*.local.yml`, `*.local.json`
  - Comment in `.gitignore` explicitly states:
    - Do **not** commit real keys in default config; keep `src/config/config.yaml` generic.
- [`src/config/config.yaml`](src/config/config.yaml:1) is sanitized:
  - Real keys have been removed and replaced with placeholders:

    ```yaml
    recognition:
      backend: groq  # local, openai, groq
      local:
        model: large-v3
        device: cuda
        compute_type: float16
        language: ru
        beam_size: 5
        temperature: 0.0
      openai:
        api_key: sk-...        # FILL LOCALLY in config.local.yaml or via UI
        model: whisper-1
        model_process: gpt-4
        language: ru
        base_url: https://api.openai.com/v1
      groq:
        api_key: gsk-...       # FILL LOCALLY in config.local.yaml or via UI
        model: whisper-large-v3
        model_process: mixtral-8x7b-32768
        language: ru
    ```

This means `config.yaml` is safe to commit to a public repository.

### Recommended workflow with git and secrets

1. **Never store real API keys in `src/config/config.yaml`.**
2. For your own keys, use one of:
   - `src/config/config.local.yaml` (preferred; ignored by git).
   - Or enter keys via the settings UI; before committing, make sure to remove them from `config.yaml` if they were saved there.
3. Recommended local config: `config.local.yaml`.

Example `src/config/config.local.yaml` (do **not** commit):

```yaml
recognition:
  openai:
    api_key: sk-YOUR_KEY
    model: whisper-1
    model_process: gpt-4o-mini
    base_url: https://api.openai.com/v1

  groq:
    api_key: gsk_YOUR_KEY
    model: whisper-large-v3
    model_process: mixtral-8x7b-32768

postprocess:
  llm_backend: groq
```

Planned improvement (not yet implemented):

- [`AppSettings.load_default()`](src/config/settings.py:132) will be extended to:
  - Load `config.yaml`.
  - If present, load `config.local.yaml`.
  - Merge `config.local.yaml` **over** `config.yaml` (local overrides default).

### Optional: `.env` support

Not implemented yet, but the codebase is ready to add `python-dotenv` and read keys from environment variables such as:

- `GROQ_API_KEY`
- `OPENAI_API_KEY`

This would be an additional option for secret management.

---

## Installation

### 1. Clone and create virtual environment

```bash
git clone <your-repo-url>
cd Voice

python -m venv .venv
.venv\Scripts\activate

pip install -r requirements.txt
```

The project targets Windows 11 and uses the default system microphone.

---

## Configuration

### 1. Base config

The base config lives in [`src/config/config.yaml`](src/config/config.yaml:1). It contains **no real keys** and can be safely committed.

Key sections:

- `recognition.backend`: `local` | `openai` | `groq`
- `recognition.local`: parameters for the local ASR backend (currently GigaAM).
- `recognition.openai`: OpenAI / OpenAI‑compatible endpoint.
- `recognition.groq`: Groq Whisper API.
- `postprocess`: LLM backend and models for text correction.
- `audio`: sample rate, channels, max duration.
- `ui`: window size, opacity, compact mode.
- `hotkeys`: global hotkey combinations.

### 2. Local overrides: `config.local.yaml`

For your own keys and machine‑specific settings, create:

```text
src/config/config.local.yaml
```

This file is ignored by `.gitignore` and should **never** be committed.

Example:

```yaml
recognition:
  backend: groq  # or openai or local

  groq:
    api_key: gsk_YOUR_KEY
    model: whisper-large-v3
    model_process: mixtral-8x7b-32768

  openai:
    api_key: sk_YOUR_KEY
    model: whisper-1
    model_process: gpt-4o-mini
    base_url: https://api.openai.com/v1

postprocess:
  llm_backend: groq
```

Planned behavior:

- `config.yaml` provides defaults.
- `config.local.yaml` overrides any subset of fields (keys, models, language, etc.).

### 3. Configure via UI

Alternatively, you can:

1. Run the app.
2. Open the settings dialog (⚙️ icon / double‑click on the floating window / tray menu).
3. Enter:
   - Recognition backend (`local`, `openai`, `groq`).
   - API keys for Groq / OpenAI.
   - Models and language.
   - Hotkeys.

Before committing, ensure that `config.yaml` does not contain real keys if the UI saved them there.

---

## Running the Application

From the project root:

```bash
.venv\Scripts\activate
python src/main.py
```

After startup:

- A system tray icon appears.
- A small floating window is shown, always on top.
- Default hotkeys (can be changed in settings):

  - `Ctrl + Win` — hold to record, release to stop.
  - `Esc` — cancel recording.
  - `Ctrl + Alt + S` — show/hide window.
  - `Ctrl + Alt + D` — toggle debug mode (partially implemented).

Workflow:

1. Focus any text field (editor, browser, messenger, etc.).
2. Hold `Ctrl + Win` and speak.
3. Release the keys.
4. The app:
   - Records audio.
   - Sends it to the selected recognition backend.
   - Optionally post‑processes the text with an LLM.
   - Copies the final text to the clipboard.
   - Simulates `Ctrl+V` into the active window.

---

## Git Usage and Safety Checklist

To keep your repository clean and free of secrets:

1. Initialize git (if not already):

   ```bash
   git init
   git add .
   git commit -m "Initial VoiceCapture MVP"
   ```

2. Before pushing to GitHub:

   - Ensure `src/config/config.yaml` contains **no real keys**.
   - Ensure no local config files are staged:

     ```bash
     git status
     git restore --staged src/config/config.local.yaml  # if it was accidentally added
     ```

3. Add remote and push:

   ```bash
   git remote add origin git@github.com:YOUR_USER/VoiceCapture.git
   git push -u origin main
   ```

---

## Roadmap / Missing Pieces vs Original Spec

The current MVP implements the full basic workflow, but some items from the original specification are still planned:

- Config and secrets:
  - [ ] Merge `config.local.yaml` over `config.yaml` in [`AppSettings.load_default()`](src/config/settings.py:132).
  - [ ] Optional `.env` support via `python-dotenv`.
- Local Whisper:
  - [ ] Add [`whisper_local.py`](src/recognition/whisper_local.py:1) using `faster-whisper`.
  - [ ] Allow choosing between GigaAM and Whisper in config/UI.
  - [ ] Add [`gpu_check.py`](src/utils/gpu_check.py:1) to detect CUDA / GPU info.
- Audio / VAD:
  - [ ] Add [`vad.py`](src/audio/vad.py:1) with simple VAD (RMS/energy).
  - [ ] Auto‑stop recording on silence > 1.5s.
- UI / UX:
  - [ ] Refine tray behavior (close to tray vs full exit).
  - [ ] Add sounds for start/stop/error (e.g. `assets/sounds/*.wav`).
- Debug:
  - [ ] Implement full debug mode in [`App.toggle_debug_mode`](src/main.py:332) (log level switch, optional debug panel).
- Tests:
  - [ ] Unit tests for audio recorder, local recognizer, clipboard, config.
  - [ ] Integration tests for end‑to‑end workflow.

---

## Development Notes

- Logging:
  - [`setup_logging`](src/utils/logger.py:1) configures loguru with rotation.
  - Transcripts are additionally logged to `logs/transcripts.log` with size‑based rotation.
- Manual LLM test:
  - [`tests/manual_llm_test.py`](tests/manual_llm_test.py:1) can be used to manually verify LLM post‑processing with your keys.

---

## License

Add your preferred license here (e.g. MIT, Apache‑2.0). Until then, the project is effectively “all rights reserved” by default.