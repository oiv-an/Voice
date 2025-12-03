# VoiceCapture

## Описание (RU)

VoiceCapture — это десктоп‑утилита для Windows, которая:
- записывает голос по глобальной горячей клавише;
- отправляет аудио в выбранный backend распознавания (Groq / OpenAI / локальный GigaAM);
- опционально прогоняет текст через LLM‑постпроцессинг (Groq или OpenAI);
- копирует итоговый текст в буфер обмена и автоматически вставляет его (Ctrl+V).

Ключевые цели текущей версии:
- единый, предсказуемый конфиг `config.yaml`;
- корректная работа всех backend’ов (Groq/OpenAI/local) для ASR и LLM;
- консистентная работа окна настроек;
- чистый, легко отлаживаемый пайплайн распознавания и постпроцессинга;
- простая и надёжная локальная интеграция GigaAM‑v3 без longform и без Hugging Face токена.

---

## Архитектура конфигурации

### Единый файл настроек

Все настройки хранятся только в одном файле:

- `config.yaml` в корне рядом с `src/` и `requirements.txt`.

Загрузка/сохранение настроек реализована в [`AppSettings.load_default()`](src/config/settings.py#L132) и [`AppSettings.save_default()`](src/config/settings.py#L277).

При первом запуске, если `config.yaml` отсутствует, он создаётся автоматически с безопасными дефолтами (см. [`App._load_or_init_settings()`](src/main.py#L349)).

### Структура AppSettings

Основной датакласс настроек — [`AppSettings`](src/config/settings.py#L121). Важные блоки:

```yaml
app:
  name: VoiceCapture
  version: 0.1.0
  language: ru
  debug: false

hotkeys:
  record: ctrl+win
  cancel: esc
  toggle_window: ctrl+alt+s
  toggle_debug: ctrl+alt+d

audio:
  device: default
  sample_rate: 16000
  channels: 1
  format: float32
  max_duration: 120
  vad_threshold: 0.5
  vad_min_duration: 0.1

recognition:
  backend: groq        # groq / openai / local
  local:
    model: large-v3
    device: cuda
    compute_type: float16
    language: ru
    beam_size: 5
    temperature: 0.0
  openai:
    api_key: sk-...
    model: gpt-4o-transcribe
    model_process: gpt-5.1
    language: ru
    base_url: https://api.voidai.app/v1
  groq:
    api_key: gsk-...
    model: whisper-large-v3
    model_process: moonshotai/kimi-k2-instruct
    language: ru

postprocess:
  enabled: true
  mode: llm            # simple / llm
  llm_backend: openai  # groq / openai
  groq:
    model: moonshotai/kimi-k2-instruct
  openai:
    model: gpt-5.1

ui:
  always_on_top: true
  opacity: 0.9
  window_size: [600, 400]
  auto_hide_after_paste: true
  hide_delay: 2000

logging:
  level: INFO
  file: app.log
  max_file_size: 10485760
  backup_count: 3
```

#### recognition.*

Определено в:

- [`OpenAIRecognitionConfig`](src/config/settings.py#L52)
- [`GroqRecognitionConfig`](src/config/settings.py#L62)
- [`LocalRecognitionConfig`](src/config/settings.py#L42)
- [`RecognitionConfig`](src/config/settings.py#L73)

Ключевые поля:

- `recognition.backend` — текущий backend распознавания (`groq` / `openai` / `local`).
- `recognition.local`:
  - `model` — идентификатор локальной модели GigaAM‑v3 (используется внутри кода, по умолчанию `large-v3`).
  - `device` — `"cuda"` или `"cpu"`; при `cuda` и отсутствии GPU автоматически падает на CPU.
  - `compute_type`, `language`, `beam_size`, `temperature` — зарезервированы под локальные модели, сейчас используются минимально.
  - **Ограничение:** локальный GigaAM‑backend обрабатывает только аудио до ~25 секунд. Всё, что длиннее, автоматически отдаётся в облачный backend (Groq/OpenAI) через каскад `_process_audio`.
- `recognition.openai`:
  - `api_key` — ключ к OpenAI‑совместимому API (или прокси).
  - `model` — модель ASR (например, `gpt-4o-transcribe`).
  - `model_process` — модель LLM для постпроцессинга (например, `gpt-5.1`).
  - `language` — язык распознавания.
  - `base_url` — **единственный** источник базового URL для OpenAI (ASR и LLM).
- `recognition.groq`:
  - `api_key` — ключ Groq.
  - `model` — модель ASR (`whisper-large-v3`).
  - `model_process` — модель LLM (`moonshotai/kimi-k2-instruct`).
  - `language` — язык распознавания.

#### postprocess.*

Определено в:

- [`GroqPostprocessConfig`](src/config/settings.py#L84)
- [`OpenAIPostprocessConfig`](src/config/settings.py#L88)
- [`PostprocessConfig`](src/config/settings.py#L93)

Содержит только:

- `enabled` — включён ли постпроцессинг.
- `mode` — `"simple"` (только regex) или `"llm"` (regex + LLM).
- `llm_backend` — `"groq"` или `"openai"`.
- `groq.model` — отображательная модель Groq LLM (для UI/конфига).
- `openai.model` — отображательная модель OpenAI LLM.

**Важно:** в `postprocess.*` **нет**:

- `api_key`
- `model_process`
- `base_url`

Все ключи, модели LLM и URL живут в `recognition.*`.

При загрузке [`AppSettings.load_default()`](src/config/settings.py#L229) выкидывает из `postprocess.groq` и `postprocess.openai` любые старые поля `api_key`, `model`, `model_process`, `base_url`, если они остались в старом `config.yaml`.

---

## Окно настроек (SettingsDialog)

Реализовано в [`SettingsDialog`](src/ui/settings_dialog.py#L22).

### Привязка полей UI к AppSettings

Загрузка значений из настроек — [`_load_from_settings`](src/ui/settings_dialog.py#L172):

- Сервис распознавания:
  - Комбо "Сервис распознавания" ↔ `settings.recognition.backend`.
- Groq API key:
  - Поле "Groq API key" ↔ `settings.recognition.groq.api_key`.
- OpenAI API key:
  - Поле "OpenAI API key" ↔ `settings.recognition.openai.api_key`.
- OpenAI Base URL:
  - Поле "OpenAI Base URL" ↔ `settings.recognition.openai.base_url`.
- Groq ASR model:
  - Поле "Groq ASR model" ↔ `settings.recognition.groq.model`.
- OpenAI ASR model:
  - Поле "OpenAI ASR model" ↔ `settings.recognition.openai.model`.
- Включение постпроцессинга:
  - Чекбокс "Включить постпроцессинг" ↔ `settings.postprocess.enabled`.
- Backend постпроцессинга:
  - Комбо "Сервис постпроцессинга" ↔ `settings.postprocess.llm_backend`.
- Groq LLM model:
  - Поле "Groq postprocess model" ↔ `settings.recognition.groq.model_process`.
- OpenAI LLM model:
  - Поле "OpenAI postprocess model" ↔ `settings.recognition.openai.model_process`.

Сохранение — [`_build_new_settings`](src/ui/settings_dialog.py#L215):

- Обновляет `RecognitionConfig`:
  - `backend` из комбо.
  - `openai.api_key`, `openai.base_url`, `openai.model`, `openai.model_process`.
  - `groq.api_key`, `groq.model`, `groq.model_process`.
- Обновляет `PostprocessConfig`:
  - `enabled` из чекбокса.
  - `llm_backend` из комбо.
  - `groq.model` и `openai.model` как отображательные значения.

Таким образом:

- OpenAI Base URL в UI ↔ **только** `recognition.openai.base_url`.
- LLM‑модели Groq/OpenAI в UI ↔ **только** `recognition.*.model_process`.

---

## Пайплайн распознавания и постпроцессинга

Основной класс приложения — [`App`](src/main.py#L18).

### Загрузка настроек и компонентов

В конструкторе:

1. Определяется `base_dir` (корень проекта или папка exe).
2. Загружается `AppSettings` через [`_load_or_init_settings`](src/main.py#L349):
   - Если `config.yaml` отсутствует — создаётся минимальный конфиг с `backend=local`.
   - Затем вызывается [`AppSettings.load_default()`](src/config/settings.py#L132).
3. Настраивается логирование [`setup_logging`](src/utils/logger.py#L1).
4. Создаются:
   - окно [`FloatingWindow`](src/ui/floating_window.py#L1),
   - иконка в трее [`SystemTrayIcon`](src/ui/system_tray.py#L1),
   - рекордер [`AudioRecorder`](src/audio/recorder.py#L1),
   - распознаватель через фабрику [`create_recognizer`](src/recognition/__init__.py#L1).

### Прокидывание настроек в TextPostprocessor

Ключевой момент — блок в [`App.__init__`](src/main.py#L52) и [`App.open_settings_dialog`](src/main.py#L155):

- Берём:
  - `post_cfg = self.settings.postprocess`
  - `rec_cfg = self.settings.recognition`
- Для Groq LLM:
  - `post_cfg.groq.api_key = rec_cfg.groq.api_key`
  - `post_cfg.groq.model_process = rec_cfg.groq.model_process` (если пусто).
- Для OpenAI LLM:
  - `post_cfg.openai.api_key = rec_cfg.openai.api_key`
  - `post_cfg.openai.model_process = rec_cfg.openai.model_process` (если пусто).
  - `post_cfg.openai.base_url = rec_cfg.openai.base_url`.

Затем создаётся:

- `self.postprocessor = TextPostprocessor(post_cfg)`.

Таким образом, `TextPostprocessor` всегда видит:

- API‑ключи из `recognition.*.api_key`.
- LLM‑модели из `recognition.*.model_process`.
- OpenAI Base URL из `recognition.openai.base_url`.

### Каскад backend’ов распознавания

Метод [`_process_audio`](src/main.py#L217):

1. Собирает список backend’ов:
   - сначала выбранный пользователем (`recognition.backend`),
   - затем остальные (`["groq", "openai", "local"]`) без дубликатов.
2. Для каждого backend’а:
   - временно подменяет `settings.recognition.backend`,
   - создаёт recognizer через `create_recognizer`,
   - вызывает `transcribe(audio_data)`.
3. При успехе — выходит из цикла, при ошибке — логирует и пробует следующий backend.
4. Если все упали — показывает последнюю ошибку.

Особенности локального backend’а GigaAM‑v3:

- Реализован в [`GigaAMRecognizer`](src/recognition/gigaam_local.py#L12).
- Использует только `model.transcribe(path)` без longform и без Hugging Face токена.
- Перед вызовом `transcribe` оценивает длительность аудио:
  - если длительность **> 25 секунд**, сразу выбрасывает контролируемый `RuntimeError("GigaAM-v3: аудио длиннее 25 секунд, используем облачный backend.")`;
  - это приводит к тому, что `_process_audio` переходит к следующему backend’у (обычно Groq).
- Если сама модель GigaAM возвращает ошибку `"Too long wav file, use 'transcribe_longform' method."`, она также заворачивается в `RuntimeError`, и каскад переходит к Groq/OpenAI.
- Таким образом, локальный GigaAM используется только для коротких запросов (до ~25 секунд), а длинные автоматически обрабатываются облаком.

### OpenAI ASR

Реализован в [`OpenAIWhisperRecognizer`](src/recognition/openai_api.py#L19):

- URL строится в [`_build_url`](src/recognition/openai_api.py#L36):

  ```python
  base = (self.config.base_url or "").strip()
  if not base:
      raise RuntimeError("OpenAI ASR: base_url не задан. Укажите 'OpenAI Base URL' в настройках.")
  base = base.rstrip("/")
  return f"{base}{OPENAI_TRANSCRIBE_PATH}"  # "/audio/transcriptions"
  ```

- Использует:
  - `recognition.openai.api_key`,
  - `recognition.openai.model`,
  - `recognition.openai.language`,
  - `recognition.openai.base_url`.

### LLM‑постпроцессинг

Реализован в [`TextPostprocessor`](src/recognition/postprocessor.py#L13).

Режимы:

- `enabled = False` → возвращает текст как есть.
- `mode = "simple"` → только regex‑очистка [`_simple_cleanup`](src/recognition/postprocessor.py#L72).
- `mode = "llm"` → regex + LLM.

#### Общая логика

Метод [`process`](src/recognition/postprocessor.py#L28):

1. Если `enabled` = False → `_simple_cleanup`.
2. Если `mode` = `"simple"` → `_simple_cleanup`.
3. Иначе:
   - делает `_simple_cleanup`,
   - проверяет наличие API‑ключа для выбранного backend’а:
     - Groq: `self.config.groq.api_key`,
     - OpenAI: `self.config.openai.api_key`.
   - если ключ пустой — логирует предупреждение и возвращает regex‑вариант.
   - иначе вызывает [`_llm_cleanup`](src/recognition/postprocessor.py#L90).
4. Любые исключения из LLM‑части ловятся, логируются, и возвращается regex‑вариант (UX не ломается).

#### Groq LLM

[`_llm_groq`](src/recognition/postprocessor.py#L108):

- API‑ключ: `self.config.groq.api_key` (из `recognition.groq.api_key`).
- Модель: `self.config.groq.model_process` (из `recognition.groq.model_process`).
- URL: жёстко `https://api.groq.com/openai/v1/chat/completions`.
- Логирует:
  - модель,
  - ошибки таймаута/сети/HTTP.

#### OpenAI LLM

[`_llm_openai`](src/recognition/postprocessor.py#L212):

- API‑ключ: `self.config.openai.api_key` (из `recognition.openai.api_key`).
- Модель:
  - сначала `self.config.openai.model_process`,
  - fallback на `self.config.openai.model`,
  - если обе пустые — явная ошибка конфигурации.
- Base URL:
  - `self.config.openai.base_url` (из `recognition.openai.base_url`, прокинутый через `App`).
  - если пустой — явная ошибка конфигурации.
- URL: `base_url.rstrip("/") + "/chat/completions"`.
- Логирует:
  - фактический URL,
  - модель,
  - первые 8 символов ключа (маскировано).

**Важно:** в коде **нет** дефолтного `https://api.openai.com/v1`. Если `base_url` не задан — это ошибка конфигурации, а не скрытый дефолт.

---

## Логирование

Используется [`loguru`](src/utils/logger.py#L1).

### Основные сообщения в консоль / app.log

- При распознавании:
  - `Trying recognition backend: {backend}`
  - `Recognition succeeded with backend: {backend}`
- При LLM‑постпроцессинге:
  - Groq:
    - `Groq LLM postprocess using model: {model}`
    - ошибки таймаута/сети/HTTP с указанием модели.
  - OpenAI:
    - `OpenAI LLM postprocess URL: {url}`
    - `OpenAI LLM postprocess using model: {model}`
    - `OpenAI LLM postprocess using api_key (first 8 chars): {prefix}***`
- При ошибках LLM:
  - `LLM postprocess failed, fallback to regex-only: {exc}`.

### Отдельный лог распознаваний (transcripts.log)

Каждое успешное распознавание дополнительно сохраняется в отдельный текстовый лог‑файл:

- Путь: `<base_dir>/logs/transcripts.log`, где:
  - `base_dir` — корень проекта при запуске из исходников;
  - либо папка рядом с `.exe` в собранной версии.
- Реализация — в методе [`App._process_audio()`](src/main.py:253).

Для каждого распознавания в `transcripts.log` пишется блок вида:

```text
[2025-12-02 11:23:45] backend=groq duration=3.524s
RAW: привет как дела
PROCESSED: Привет, как дела?
----------------------------------------
```

Где:

- `timestamp` — время завершения распознавания;
- `backend` — фактический backend, который вернул результат (`groq` / `openai` / `local`);
- `duration` — длительность аудио в секундах (по числу сэмплов и sample_rate);
- `RAW` — исходный текст от ASR;
- `PROCESSED` — текст после постобработки (regex + LLM, если включён).

#### Ротация transcripts.log

- Если размер `transcripts.log` достигает ~3 МБ:
  - текущий файл переименовывается в `transcripts_YYYYMMDD_HHMMSS.log`;
  - создаётся новый `transcripts.log`.
- Это позволяет хранить историю распознаваний без бесконечного роста файла.

---

## Как использовать

### Установка

```bash
pip install -r requirements.txt
```

### Запуск

```bash
python src/main.py
```

При первом запуске:

- создастся `config.yaml` в корне;
- backend по умолчанию — `local` (GigaAM);
- локальный GigaAM будет использоваться только для коротких записей (до ~25 секунд);
- для Groq/OpenAI нужно будет вручную ввести ключи и (для OpenAI) `base_url`.

### Настройка backend’ов

1. Открыть окно настроек (иконка ⚙️).
2. В блоке "Сервис распознавания":
   - выбрать `Groq` или `OpenAI` или `GigaAM-v3 (local)`;
   - заполнить `Groq API key` и/или `OpenAI API key`;
   - для OpenAI указать `OpenAI Base URL` (например, `https://api.voidai.app/v1`).
3. В блоке "Модели распознавания (ASR)":
   - указать модели Groq/OpenAI ASR.
4. В блоке "Постобработка текста (LLM)":
   - включить чекбокс "Включить постпроцессинг";
   - выбрать backend постпроцессинга (`Groq` или `OpenAI`);
   - указать модели LLM:
     - `Groq postprocess model` ↔ `recognition.groq.model_process`;
     - `OpenAI postprocess model` ↔ `recognition.openai.model_process`.
5. Нажать OK — настройки сохранятся в `config.yaml`, recognizer и postprocessor будут пересозданы.

---

## Тестирование LLM‑постпроцессинга

Есть отдельный скрипт [`tests/manual_llm_test.py`](tests/manual_llm_test.py#L1):

```bash
python tests/manual_llm_test.py
```

Он:

- загружает `AppSettings` так же, как основное приложение;
- печатает текущие настройки LLM;
- создаёт `TextPostprocessor` и прогоняет тестовый текст;
- показывает, сработал ли LLM или был fallback на исходный текст.

---

## GitHub

Проект рассчитан на выкладку в публичный репозиторий GitHub. Для этого:

1. Убедитесь, что `config.yaml` добавлен в `.gitignore` и не содержит реальных ключей.
2. В README (этот файл) описана актуальная архитектура конфигурации и пайплайна.
3. Для публикации:
   - создайте репозиторий на GitHub;
   - добавьте этот проект;
   - запушьте изменения.

---

# VoiceCapture (EN)

## Overview

VoiceCapture is a Windows desktop utility that:

- records your voice using a global hotkey;
- sends audio to a selected recognition backend (Groq / OpenAI / local GigaAM);
- optionally runs the text through an LLM post‑processor (Groq or OpenAI);
- copies the final text to the clipboard and auto‑pastes it (Ctrl+V).

In the final version:

- the local GigaAM‑v3 backend is used only for short audio (up to ~25 seconds);
- longer recordings are automatically handled by cloud backends (Groq/OpenAI);
- there is no Hugging Face token or longform integration in the app code.

Current version goals:

- a single, predictable `config.yaml`;
- correct behavior of all ASR and LLM backends (Groq/OpenAI/local);
- consistent settings dialog behavior;
- a clean, debuggable recognition + post‑processing pipeline.

---

## Configuration Architecture

### Single config file

All settings live in a single file:

- `config.yaml` in the project root (next to `src/` and `requirements.txt`).

Loading/saving is implemented in [`AppSettings.load_default()`](src/config/settings.py#L132) and [`AppSettings.save_default()`](src/config/settings.py#L277).

On first run, if `config.yaml` does not exist, it is created with safe defaults (see [`App._load_or_init_settings()`](src/main.py#L349)).

### AppSettings structure

Main settings dataclass: [`AppSettings`](src/config/settings.py#L121).

Important blocks:

- `app`, `hotkeys`, `audio`, `ui`, `logging` — straightforward.
- `recognition` — all ASR and LLM **keys/models/URLs** live here.
- `postprocess` — only flags and display models, no keys or URLs.

See the YAML example above in the Russian section; it is the same structure.

#### recognition.*

Defined in:

- [`OpenAIRecognitionConfig`](src/config/settings.py#L52)
- [`GroqRecognitionConfig`](src/config/settings.py#L62)
- [`LocalRecognitionConfig`](src/config/settings.py#L42)
- [`RecognitionConfig`](src/config/settings.py#L73)

Key fields:

- `recognition.backend` — current ASR backend (`groq` / `openai` / `local`).
- `recognition.openai`:
  - `api_key` — OpenAI‑compatible (or proxy) API key.
  - `model` — ASR model (e.g. `gpt-4o-transcribe`).
  - `model_process` — LLM model for post‑processing (e.g. `gpt-5.1`).
  - `language` — recognition language.
  - `base_url` — **single** source of truth for OpenAI base URL (used by both ASR and LLM).
- `recognition.groq`:
  - `api_key` — Groq key.
  - `model` — ASR model (`whisper-large-v3`).
  - `model_process` — LLM model (`moonshotai/kimi-k2-instruct`).
  - `language` — recognition language.

#### postprocess.*

Defined in:

- [`GroqPostprocessConfig`](src/config/settings.py#L84)
- [`OpenAIPostprocessConfig`](src/config/settings.py#L88)
- [`PostprocessConfig`](src/config/settings.py#L93)

Contains only:

- `enabled` — whether post‑processing is enabled.
- `mode` — `"simple"` (regex only) or `"llm"` (regex + LLM).
- `llm_backend` — `"groq"` or `"openai"`.
- `groq.model` — display Groq LLM model.
- `openai.model` — display OpenAI LLM model.

**Important:** `postprocess.*` does **not** contain:

- `api_key`
- `model_process`
- `base_url`

All keys, LLM models and URLs live in `recognition.*`.

On load, [`AppSettings.load_default()`](src/config/settings.py#L229) drops any legacy `api_key`, `model`, `model_process`, `base_url` fields from `postprocess.groq` and `postprocess.openai`.

---

## Settings Dialog

Implemented in [`SettingsDialog`](src/ui/settings_dialog.py#L22).

### UI ↔ AppSettings mapping

Loading from settings — [`_load_from_settings`](src/ui/settings_dialog.py#L172):

- Recognition service combo ↔ `settings.recognition.backend`.
- Groq API key field ↔ `settings.recognition.groq.api_key`.
- OpenAI API key field ↔ `settings.recognition.openai.api_key`.
- OpenAI Base URL field ↔ `settings.recognition.openai.base_url`.
- Groq ASR model field ↔ `settings.recognition.groq.model`.
- OpenAI ASR model field ↔ `settings.recognition.openai.model`.
- Postprocess enabled checkbox ↔ `settings.postprocess.enabled`.
- Postprocess backend combo ↔ `settings.postprocess.llm_backend`.
- Groq postprocess model field ↔ `settings.recognition.groq.model_process`.
- OpenAI postprocess model field ↔ `settings.recognition.openai.model_process`.

Saving — [`_build_new_settings`](src/ui/settings_dialog.py#L215):

- Updates `RecognitionConfig` with API keys, base URL, ASR models and LLM models.
- Updates `PostprocessConfig` with:
  - `enabled`, `llm_backend`,
  - display models `groq.model` and `openai.model`.

So:

- OpenAI Base URL in UI ↔ **only** `recognition.openai.base_url`.
- Groq/OpenAI LLM models in UI ↔ **only** `recognition.*.model_process`.

---

## Recognition and Post‑processing Pipeline

Main application class — [`App`](src/main.py#L18).

### Settings and components

In `__init__`:

1. Determine `base_dir` (project root or exe folder).
2. Load `AppSettings` via [`_load_or_init_settings`](src/main.py#L349).
3. Configure logging via [`setup_logging`](src/utils/logger.py#L1).
4. Create:
   - main window [`FloatingWindow`](src/ui/floating_window.py#L1),
   - tray icon [`SystemTrayIcon`](src/ui/system_tray.py#L1),
   - recorder [`AudioRecorder`](src/audio/recorder.py#L1),
   - recognizer via [`create_recognizer`](src/recognition/__init__.py#L1).

### Wiring settings into TextPostprocessor

In both [`App.__init__`](src/main.py#L52) and [`App.open_settings_dialog`](src/main.py#L155):

- `post_cfg = self.settings.postprocess`
- `rec_cfg = self.settings.recognition`

For Groq LLM:

- `post_cfg.groq.api_key = rec_cfg.groq.api_key`
- `post_cfg.groq.model_process = rec_cfg.groq.model_process` (if empty).

For OpenAI LLM:

- `post_cfg.openai.api_key = rec_cfg.openai.api_key`
- `post_cfg.openai.model_process = rec_cfg.openai.model_process` (if empty).
- `post_cfg.openai.base_url = rec_cfg.openai.base_url`.

Then:

- `self.postprocessor = TextPostprocessor(post_cfg)`.

Thus `TextPostprocessor` always sees:

- API keys from `recognition.*.api_key`,
- LLM models from `recognition.*.model_process`,
- OpenAI base URL from `recognition.openai.base_url`.

### Backend cascade

[`_process_audio`](src/main.py#L217):

- Builds an ordered list of backends:
  - primary from `recognition.backend`,
  - then `["groq", "openai", "local"]` without duplicates.
- For each backend:
  - temporarily sets `settings.recognition.backend`,
  - creates recognizer via `create_recognizer`,
  - calls `transcribe(audio_data)`.
- On success — stops; on error — logs and tries next backend.
- If all fail — shows the last error.

### OpenAI ASR

[`OpenAIWhisperRecognizer`](src/recognition/openai_api.py#L19):

- `_build_url()` uses only `recognition.openai.base_url`:
  - if empty → configuration error.
  - otherwise → `base_url.rstrip("/") + "/audio/transcriptions"`.

### LLM Post‑processing

[`TextPostprocessor`](src/recognition/postprocessor.py#L13):

- `enabled = False` → original text.
- `mode = "simple"` → regex only.
- `mode = "llm"` → regex + LLM.

Common logic in [`process`](src/recognition/postprocessor.py#L28):

- If no API key for selected backend → warning + regex only.
- Any LLM exception → logged + regex only.

Groq LLM — [`_llm_groq`](src/recognition/postprocessor.py#L108):

- API key from `recognition.groq.api_key`.
- Model from `recognition.groq.model_process`.
- URL: `https://api.groq.com/openai/v1/chat/completions`.

OpenAI LLM — [`_llm_openai`](src/recognition/postprocessor.py#L212):

- API key from `recognition.openai.api_key`.
- Model from `recognition.openai.model_process` with fallback to `recognition.openai.model`.
- Base URL from `recognition.openai.base_url` (wired via `post_cfg.openai.base_url`).
- URL: `base_url.rstrip("/") + "/chat/completions"`.
- No hardcoded `https://api.openai.com/v1` anywhere.

---

## Logging

Using [`loguru`](src/utils/logger.py#L1).

Key logs:

- ASR:
  - `Trying recognition backend: {backend}`
  - `Recognition succeeded with backend: {backend}`
- LLM:
  - Groq:
    - `Groq LLM postprocess using model: {model}`
    - detailed timeout/network/HTTP errors.
  - OpenAI:
    - `OpenAI LLM postprocess URL: {url}`
    - `OpenAI LLM postprocess using model: {model}`
    - `OpenAI LLM postprocess using api_key (first 8 chars): {prefix}***`
- Fallback:
  - `LLM postprocess failed, fallback to regex-only: {exc}`.

---

## Usage

### Install

```bash
pip install -r requirements.txt
```

### Run

```bash
python src/main.py
```

On first run:

- `config.yaml` is created in the project root.
- Default backend is `local` (GigaAM).
- Local GigaAM is used only for short recordings (up to ~25 seconds); longer ones will fall back to Groq/OpenAI.
- You must manually set API keys and (for OpenAI) `base_url`.

### Configure backends

1. Open settings dialog (⚙️).
2. In "Recognition service":
   - choose `Groq`, `OpenAI` or `GigaAM-v3 (local)`;
   - fill `Groq API key` and/or `OpenAI API key`;
   - for OpenAI, set `OpenAI Base URL` (e.g. `https://api.voidai.app/v1`).
3. In "ASR models":
   - set Groq/OpenAI ASR models.
4. In "Text post‑processing (LLM)":
   - enable "Enable postprocessing";
   - choose postprocess backend (`Groq` or `OpenAI`);
   - set LLM models:
     - `Groq postprocess model` ↔ `recognition.groq.model_process`;
     - `OpenAI postprocess model` ↔ `recognition.openai.model_process`.
5. Click OK — settings are saved to `config.yaml`, recognizer and postprocessor are recreated.

---

## Manual LLM test

Use [`tests/manual_llm_test.py`](tests/manual_llm_test.py#L1):

```bash
python tests/manual_llm_test.py
```

It:

- loads `AppSettings` the same way as the app;
- prints current LLM settings;
- runs `TextPostprocessor.process()` on a test string;
- shows whether LLM actually changed the text or fallback was used.

---

## GitHub

To publish this project on GitHub:

1. Ensure `config.yaml` is in `.gitignore` and does not contain real API keys.
2. Commit the source code and this updated `README.md`.
3. Push to your GitHub repository.

This README describes the current configuration model and the recognition + post‑processing pipeline, including the unified handling of OpenAI/Groq backends and the single source of truth for `base_url` and models.