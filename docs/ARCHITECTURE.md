# VoiceCapture Architecture

This document describes the internal architecture of VoiceCapture: how modules are structured, how data flows through the system, and how configuration and backends are wired together.

The goal is to give a new contributor enough context to navigate the codebase and safely extend it.

---

## 1. High‑Level Overview

VoiceCapture is a small desktop utility that:

1. Listens for global hotkeys.
2. Records audio from the system microphone.
3. Sends audio to a speech‑to‑text backend (Groq, OpenAI, or local).
4. Optionally post‑processes the text with an LLM.
5. Copies the result to the clipboard and simulates `Ctrl+V` into the active window.
6. Shows status and text in a floating always‑on‑top window and a system tray icon.

Main entry point:

- [`src/main.py`](src/main.py)
  - Defines the `App` class, which wires together:
    - Configuration (`AppSettings`)
    - Audio recorder
    - Recognition backend
    - Text post‑processor
    - Clipboard manager
    - UI (floating window + tray)
    - Hotkey manager
    - Logging

---

## 2. Configuration Layer

### 2.1. AppSettings and Config Dataclasses

File: [`src/config/settings.py`](src/config/settings.py:1)

Key components:

- `HotkeysConfig`
- `AudioConfig`
- `UIConfig`
- `RecognitionLocalConfig`
- `OpenAIRecognitionConfig`
- `GroqRecognitionConfig`
- `PostprocessConfig`
- `AppSettings`

`AppSettings` is the root configuration object. It is responsible for:

- Loading YAML configuration from `src/config/config.yaml` (and later `config.local.yaml`).
- Validating and normalizing values.
- Providing typed access to all settings.

Important methods:

- [`AppSettings.load_default()`](src/config/settings.py:132)
  - Currently:
    - Loads `config.yaml`.
  - Planned:
    - Load `config.yaml`.
    - If present, load `config.local.yaml`.
    - Merge `config.local.yaml` **over** `config.yaml` so local values override defaults.

### 2.2. YAML Files

- Default config: [`src/config/config.yaml`](src/config/config.yaml:1)
  - Contains **no real API keys**.
  - Safe to commit to GitHub.
  - Defines:
    - `recognition.backend` (`local` | `openai` | `groq`)
    - `recognition.local` (model, device, compute_type, language, beam_size, temperature)
    - `recognition.openai` (api_key placeholder, model, model_process, base_url, language)
    - `recognition.groq` (api_key placeholder, model, model_process, language)
    - `postprocess` (LLM backend and models)
    - `audio` (sample rate, channels, max duration)
    - `ui` (window size, opacity, compact mode)
    - `hotkeys` (global hotkey combinations)

- Local overrides (planned, not yet wired in code):
  - `src/config/config.local.yaml`
    - Ignored by `.gitignore`.
    - Intended to hold real API keys and machine‑specific overrides.

---

## 3. Main Application Orchestration

File: [`src/main.py`](src/main.py:1)

### 3.1. App Lifecycle

Class: `App`

Key responsibilities:

1. Initialize logging via [`setup_logging`](src/utils/logger.py:1).
2. Load configuration via `AppSettings.load_default()`.
3. Create and wire:
   - `AudioRecorder`
   - Recognition backend (via `create_recognizer`)
   - `TextPostprocessor`
   - `ClipboardManager`
   - `FloatingWindow`
   - `SystemTrayIcon`
   - `HotKeyManager`
4. Connect signals/slots between UI, hotkeys, and core logic.
5. Implement the main workflow:
   - Start recording on hotkey press.
   - Stop recording on hotkey release.
   - Run recognition and post‑processing.
   - Copy & paste result.
   - Update UI state and logs.

Important methods (line numbers approximate):

- [`App.__init__`](src/main.py:34)
  - Loads config.
  - Creates UI components.
  - Creates recorder, recognizer, postprocessor, clipboard.
  - Sets up hotkeys and connects signals.

- [`App.start_recording`](src/main.py:178)
  - Called when the record hotkey is pressed.
  - Updates UI state to `recording`.
  - Starts `AudioRecorder`.

- [`App.stop_recording`](src/main.py:191)
  - Called when the record hotkey is released.
  - Stops `AudioRecorder`.
  - Triggers `_process_audio` in a background task.

- [`App._process_audio`](src/main.py:206)
  - Core pipeline:
    1. Reads recorded audio.
    2. Sends it to the recognizer.
    3. Runs `_simple_cleanup` and LLM post‑processing via `TextPostprocessor`.
    4. Updates UI with raw and processed text.
    5. Uses `ClipboardManager` to copy and paste the processed text.
    6. Logs transcript to `logs/transcripts.log`.

- [`App.toggle_debug_mode`](src/main.py:332)
  - Currently a stub:
    - Shows a message in the window.
  - Planned:
    - Toggle log level (INFO/DEBUG).
    - Optionally show a debug panel or log viewer.

---

## 4. Audio Subsystem

File: [`src/audio/recorder.py`](src/audio/recorder.py:1)

Class: `AudioRecorder`

Responsibilities:

- Manage audio capture from the default input device using `sounddevice.InputStream`.
- Store audio in memory for later processing.
- Respect configuration from `AudioConfig`:
  - `sample_rate`
  - `channels`
  - `max_duration`

Key points:

- Format: `float32` samples.
- Recording loop:
  - Appends incoming audio chunks to an internal buffer.
  - Stops when:
    - `stop()` is called by `App.stop_recording()`, or
    - `max_duration` is reached.
- Conversion to WAV:
  - Recognition backends (`groq_api`, `openai_api`, `gigaam_local`) handle conversion to WAV or tensor formats as needed.

Planned extensions:

- [`audio/vad.py`](src/audio/vad.py:1) (not yet implemented):
  - Simple VAD based on RMS/energy.
  - Auto‑stop recording when silence > 1.5s.
  - Integration into the recording loop to stop on silence instead of only manual stop / max duration.

---

## 5. Recognition Backends

Directory: [`src/recognition/`](src/recognition/__init__.py:1)

### 5.1. Factory

File: [`src/recognition/__init__.py`](src/recognition/__init__.py:1)

Function: `create_recognizer(settings: AppSettings)`

- Reads `settings.recognition.backend`:
  - `"groq"` → `GroqWhisperRecognizer`
  - `"openai"` → `OpenAIWhisperRecognizer`
  - `"local"` → `GigaAMRecognizer` (currently; Whisper planned)
- Passes relevant config sections to the chosen recognizer.

### 5.2. Groq Whisper API

File: [`src/recognition/groq_api.py`](src/recognition/groq_api.py:1)

Class: `GroqWhisperRecognizer`

- Endpoint: `https://api.groq.com/openai/v1/audio/transcriptions`
- Uses:
  - `recognition.groq.api_key`
  - `recognition.groq.model`
  - `recognition.groq.language`
- Responsibilities:
  - Convert recorded audio to WAV.
  - Send multipart/form‑data request to Groq.
  - Handle:
    - Timeouts
    - Network errors
    - HTTP 401 / 429 / other errors
  - Return recognized text.

### 5.3. OpenAI Whisper / OpenAI‑Compatible API

File: [`src/recognition/openai_api.py`](src/recognition/openai_api.py:1)

Class: `OpenAIWhisperRecognizer`

- Endpoint: `{base_url}/audio/transcriptions`
  - `base_url` from `recognition.openai.base_url`.
  - Allows using:
    - Official OpenAI API.
    - Self‑hosted / compatible endpoints (e.g. VoidAI).
- Uses:
  - `recognition.openai.api_key`
  - `recognition.openai.model`
  - `recognition.openai.language`
- Responsibilities:
  - Same as Groq recognizer, but with OpenAI‑style API.

### 5.4. Local ASR (GigaAM)

File: [`src/recognition/gigaam_local.py`](src/recognition/gigaam_local.py:12)

Class: `GigaAMRecognizer`

- Uses `transformers.AutoModel` to load a local GigaAM‑v3 model.
- Runs inference on the recorded audio locally (CPU/GPU depending on config).
- Config:
  - `recognition.local.model`
  - `recognition.local.device`
  - `recognition.local.compute_type`
  - `recognition.local.language`
  - `recognition.local.beam_size`
  - `recognition.local.temperature`

This is not Whisper, but functionally satisfies “local ASR backend”.

### 5.5. Planned: Local Whisper via faster‑whisper

File (planned): [`src/recognition/whisper_local.py`](src/recognition/whisper_local.py:1)

- Implementation idea:
  - Use `faster-whisper` to load a Whisper model.
  - Respect `recognition.local` parameters:
    - `model`
    - `device`
    - `compute_type`
    - `language`
    - `beam_size`
    - `temperature`
- Factory extension:
  - Add `recognition.local.engine: "gigaam" | "whisper"`.
  - `create_recognizer()` chooses between `GigaAMRecognizer` and `WhisperLocalRecognizer`.

### 5.6. GPU Detection

File (planned): [`src/utils/gpu_check.py`](src/utils/gpu_check.py:1)

- Functions:
  - `has_cuda()`
  - `get_gpu_info()`
- Usage:
  - Local ASR backends can:
    - Prefer GPU when available.
    - Warn user if GPU is not detected but `device=cuda` is configured.

---

## 6. Text Post‑Processing

File: [`src/recognition/postprocessor.py`](src/recognition/postprocessor.py:1)

Class: `TextPostprocessor`

Responsibilities:

1. Simple cleanup:
   - `_simple_cleanup(text)`:
     - Regex‑based normalization.
     - Trims whitespace, fixes common artifacts from ASR.
2. LLM‑based correction (optional):
   - Uses `postprocess.llm_backend`:
     - `"groq"` → Groq LLM (e.g. Mixtral).
     - `"openai"` → OpenAI LLM (e.g. GPT‑4).
   - Uses:
     - `postprocess.groq.model_process`
     - `postprocess.openai.model_process`
   - **API keys are taken from recognition config**:
     - `recognition.groq.api_key`
     - `recognition.openai.api_key`
   - Prompt:
     - Fix typos and punctuation.
     - Do not change the meaning of the text.

Integration in `App`:

- In [`App._process_audio`](src/main.py:268):
  1. `raw_text = recognizer.transcribe(audio)`
  2. `clean_text = self.postprocessor._simple_cleanup(raw_text)`
  3. `processed_text = self.postprocessor.process(raw_text)` (LLM)
  4. UI shows both:
     - `set_raw_text(raw_text)`
     - `set_processed_text(processed_text)`

---

## 7. Clipboard and Keyboard Simulation

File: [`src/clipboard/clipboard_manager.py`](src/clipboard/clipboard_manager.py:1)

Class: `ClipboardManager`

Responsibilities:

- Copy text to the system clipboard using `pyperclip`.
- Simulate `Ctrl+V` into the active window using `pynput`.
- Implement retries and small delays to make paste more reliable.

Usage in `App`:

- In [`App._process_audio`](src/main.py:295):
  - `self.clipboard.copy(processed_text)`
  - `self.clipboard.paste()`

This allows the user to simply hold the hotkey, speak, and have the text appear in the active application.

---

## 8. UI Layer

Directory: [`src/ui/`](src/ui/floating_window.py:1)

### 8.1. Floating Window

File: [`src/ui/floating_window.py`](src/ui/floating_window.py:33)

Class: `FloatingWindow` (PySide6 widget)

Features:

- Frameless, always‑on‑top, translucent window:
  - [`_init_window_flags`](src/ui/floating_window.py:74)
- Size and opacity from `UIConfig`:
  - [`_apply_config`](src/ui/floating_window.py:200)
- Draggable:
  - [`mousePressEvent`](src/ui/floating_window.py:344)
  - [`mouseMoveEvent`](src/ui/floating_window.py:350)
- Double‑click:
  - [`mouseDoubleClickEvent`](src/ui/floating_window.py:360)
  - Emits `settings_requested` signal.
- States:
  - `idle`, `recording`, `processing`, `ready`, `error`
  - [`set_state`](src/ui/floating_window.py:209) updates icons/emoji and text.
- Compact mode:
  - [`set_compact`](src/ui/floating_window.py:249)
  - [`_apply_compact_mode`](src/ui/floating_window.py:259)
  - Shows a minimal microphone icon.

Signals:

- `settings_requested`
- `exit_requested`
- `copy_requested` (if user clicks on text blocks, etc.)

Planned enhancements:

- Play sounds on state changes (start/stop/error) using `assets/sounds/*.wav`.

### 8.2. System Tray

File: [`src/ui/system_tray.py`](src/ui/system_tray.py:1)

Class: `SystemTrayIcon`

Features:

- Tray icon with context menu.
- Signals:
  - `show_window_requested`
  - `settings_requested`
  - `toggle_debug_requested`
  - `exit_requested`

Integration:

- In [`App.__init__`](src/main.py:34):
  - Tray is created and signals are connected to `App` methods.

Planned behavior:

- “Close to tray”:
  - Clicking ✖️ in the window hides it but keeps the app running in the tray.
  - Tray menu provides “Exit” for full shutdown.

### 8.3. Settings Dialog

File: [`src/ui/settings_dialog.py`](src/ui/settings_dialog.py:1)

Class: `SettingsDialog`

Responsibilities:

- Provide a UI for editing:
  - Recognition backend (`local/openai/groq`).
  - API keys for Groq / OpenAI.
  - Models and language.
  - Hotkeys.
- Save changes back to `AppSettings` and persist them to YAML.

This dialog is opened from:

- Double‑click on `FloatingWindow`.
- Tray menu.
- Possibly other UI elements.

---

## 9. Hotkeys

Directory: [`src/hotkey/`](src/hotkey/hotkey_manager.py:1)

File: [`src/hotkey/hotkey_manager.py`](src/hotkey/hotkey_manager.py:1)

Class: `HotKeyManager`

Responsibilities:

- Register global hotkeys using `pynput`.
- Map key combinations from `HotkeysConfig` to callbacks in `App`.

Default hotkeys (configurable):

- `record` — `Ctrl + Win` (press = start, release = stop).
- `cancel` — `Esc`.
- `show_window` — `Ctrl + Alt + S`.
- `toggle_debug` — `Ctrl + Alt + D`.

Integration:

- In [`App.__init__`](src/main.py:79):
  - `HotKeyManager` is created with all combinations from config.
  - Callbacks are bound to `App.start_recording`, `App.stop_recording`, `App.toggle_debug_mode`, etc.

---

## 10. Logging and Debugging

Directory: [`src/utils/`](src/utils/logger.py:1)

File: [`src/utils/logger.py`](src/utils/logger.py:1)

Function: `setup_logging()`

- Uses `loguru` for logging.
- Configures:
  - Console logging.
  - File logging with rotation (e.g. `app.log`).
- In `_process_audio`, transcripts are additionally logged to:
  - `logs/transcripts.log` with rotation at ~3 MB.

Debug mode:

- Toggled via:
  - Hotkey (`toggle_debug`).
  - Tray menu.
- Current implementation:
  - Only shows a message in the floating window.
- Planned:
  - Switch log level between INFO and DEBUG.
  - Optionally show a debug overlay or log viewer.

---

## 11. Tests

Directory: [`tests/`](tests/manual_llm_test.py:1)

Current tests:

- [`tests/manual_llm_test.py`](tests/manual_llm_test.py:1)
  - Manual test for LLM post‑processing.
  - Useful for verifying Groq/OpenAI integration with your keys.

Planned tests:

- Unit tests:
  - `test_audio_recorder.py` — basic recording and buffer behavior.
  - `test_whisper_local.py` — local Whisper backend (once implemented).
  - `test_clipboard.py` — clipboard copy/paste logic (with mocks).
  - `test_config.py` — config loading and `config.local.yaml` merge.
- Integration tests:
  - End‑to‑end workflow:
    - Simulate audio input.
    - Run through recognizer and postprocessor.
    - Verify clipboard content.

---

## 12. Extensibility Guidelines

### 12.1. Adding a New Recognition Backend

1. Create a new file in `src/recognition/`, e.g. [`my_backend.py`](src/recognition/my_backend.py:1).
2. Implement a recognizer class with a `transcribe(audio_bytes | np.ndarray) -> str` method.
3. Add configuration fields to:
   - `AppSettings` / `Recognition*Config` in [`settings.py`](src/config/settings.py:1).
   - `config.yaml` (with placeholders, no real keys).
4. Extend `create_recognizer()` in [`__init__.py`](src/recognition/__init__.py:1) to handle the new backend.
5. Optionally extend `SettingsDialog` to allow selecting and configuring the new backend.

### 12.2. Adding New UI Elements

- Use PySide6 widgets in:
  - [`floating_window.py`](src/ui/floating_window.py:33) for always‑on‑top UI.
  - [`settings_dialog.py`](src/ui/settings_dialog.py:1) for configuration.
- Expose new actions via:
  - Signals from UI to `App`.
  - Methods in `App` that perform the actual logic.

### 12.3. Working with Config and Secrets

- Never hard‑code API keys in code or in `config.yaml`.
- Use:
  - `config.local.yaml` (ignored by git).
  - Environment variables (once `.env` support is added).
  - UI input that is sanitized before commit.

---

## 13. Summary

- `App` in [`src/main.py`](src/main.py:34) is the central orchestrator.
- Configuration is handled by `AppSettings` in [`src/config/settings.py`](src/config/settings.py:121) with YAML files in `src/config/`.
- Audio is captured by `AudioRecorder` in [`src/audio/recorder.py`](src/audio/recorder.py:21).
- Recognition backends live in `src/recognition/` and are selected by `create_recognizer()`.
- Text post‑processing is done by `TextPostprocessor` in [`src/recognition/postprocessor.py`](src/recognition/postprocessor.py:1).
- Clipboard operations are handled by `ClipboardManager` in [`src/clipboard/clipboard_manager.py`](src/clipboard/clipboard_manager.py:1).
- UI is implemented with PySide6 in `src/ui/` (floating window, tray, settings dialog).
- Hotkeys are managed by `HotKeyManager` in [`src/hotkey/hotkey_manager.py`](src/hotkey/hotkey_manager.py:1).
- Logging is configured by `setup_logging` in [`src/utils/logger.py`](src/utils/logger.py:1).

This structure should make it straightforward to extend the app with new backends, UI features, and configuration options while keeping secrets safe and the public repository clean.