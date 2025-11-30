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