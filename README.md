# VoiceCapture 2.1

VoiceCapture 2.1 — это легковесная портативная утилита для голосового ввода и обработки текста с использованием облачных API (Groq, OpenAI).

## Особенности

*   **Портативность:** Работает из одного исполняемого файла, не требует установки.
*   **Crash Recovery:** Автоматическое сохранение и восстановление записей при сбоях.
*   **Ускорение x2:** Автоматическое ускорение аудио для экономии трафика и быстрого распознавания.
*   **Выбор микрофона:** Возможность выбора конкретного устройства ввода в настройках.
*   **Облачное распознавание:** Поддержка Groq (Whisper) и OpenAI (Whisper).
*   **Постобработка:** Автоматическое улучшение текста с помощью LLM (исправление пунктуации, стиля и т.д.).
*   **Глобальные горячие клавиши:** Удобное управление записью из любого приложения.
*   **Буфер обмена:** Автоматическое копирование и вставка распознанного текста.

## Установка и запуск

1.  Скачайте исполняемый файл `VoiceCapture.exe`.
2.  Запустите файл.
3.  При первом запуске откройте настройки (иконка шестеренки) и введите API-ключ для выбранного сервиса (Groq или OpenAI).

### Получение API ключа Groq (Бесплатно)

Groq предоставляет щедрые бесплатные лимиты для разработчиков. Это отличный способ начать использовать приложение бесплатно.

1.  Перейдите на [console.groq.com](https://console.groq.com).
2.  Зарегистрируйтесь или войдите в систему.
3.  Создайте новый API ключ в разделе "API Keys".
4.  Скопируйте ключ и вставьте его в настройки VoiceCapture.

## Использование

*   **Запись:** Нажмите `Ctrl + Win` (по умолчанию) для начала записи. Отпустите клавиши для завершения.
*   **Запись идеи:** Нажмите `Ctrl + Win + Alt` для записи "идеи" (сохраняется в отдельный лог).
*   **Отмена:** Нажмите `Esc` во время записи для отмены.

## Настройка

В настройках можно изменить:
*   Сервис распознавания (Groq, OpenAI).
*   API-ключи.
*   Модели распознавания и постобработки.
*   Горячие клавиши.
*   Параметры аудио (устройство, частота дискретизации и т.д.).

## Сборка из исходников

Для сборки портативной версии (exe) требуется Python 3.12+.

1.  Установите зависимости:
    ```bash
    pip install -r requirements.txt
    ```
2.  Запустите скрипт сборки:
    ```bash
    python build_exe.py
    ```
3.  Готовый файл будет находиться в папке `dist`.

---

# VoiceCapture 2.1 (English)

VoiceCapture 2.1 is a lightweight portable utility for voice typing and text processing using cloud APIs (Groq, OpenAI).

## Features

*   **Portability:** Runs from a single executable file, no installation required.
*   **Crash Recovery:** Automatic saving and recovery of recordings in case of crashes.
*   **x2 Speedup:** Automatic audio speedup to save traffic and speed up recognition.
*   **Microphone Selection:** Ability to select a specific input device in settings.
*   **Cloud Recognition:** Support for Groq (Whisper) and OpenAI (Whisper).
*   **Post-processing:** Automatic text improvement using LLM (punctuation correction, style, etc.).
*   **Global Hotkeys:** Convenient recording control from any application.
*   **Clipboard:** Automatic copying and pasting of recognized text.

## Installation and Launch

1.  Download the `VoiceCapture.exe` executable file.
2.  Run the file.
3.  On first launch, open settings (gear icon) and enter the API key for the selected service (Groq or OpenAI).

### Getting Groq API Key (Free)

Groq provides generous free tiers for developers. This is a great way to start using the app for free.

1.  Go to [console.groq.com](https://console.groq.com).
2.  Sign up or log in.
3.  Create a new API key in the "API Keys" section.
4.  Copy the key and paste it into VoiceCapture settings.

## Usage

*   **Record:** Press `Ctrl + Win` (default) to start recording. Release keys to stop.
*   **Record Idea:** Press `Ctrl + Win + Alt` to record an "idea" (saved to a separate log).
*   **Cancel:** Press `Esc` during recording to cancel.

## Settings

In settings you can change:
*   Recognition service (Groq, OpenAI).
*   API keys.
*   Recognition and post-processing models.
*   Hotkeys.
*   Audio parameters (device, sample rate, etc.).

## Build from Source

To build the portable version (exe), Python 3.12+ is required.

1.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
2.  Run build script:
    ```bash
    python build_exe.py
    ```
3.  The finished file will be in the `dist` folder.