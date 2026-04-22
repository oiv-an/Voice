# Build in Public — VoiceCapture v2.4.0

Короткий пост про апдейт. Можно использовать для Telegram / Twitter / LinkedIn / Хабра.

---

## Вариант 1 — короткий (для Telegram / Twitter)

🎙️ **VoiceCapture v2.4.0** — добавил третий бекенд распознавания: **OpenRouter (Gemini)**.

Теперь в одном .exe'шнике живут сразу 3 ASR:
— Groq Whisper
— OpenAI Whisper
— **OpenRouter / google/gemini-3.1-flash-lite-preview** (новое)

Главная фишка — OpenRouter не использует классический multipart `POST /audio/transcriptions`. Там аудио летит **в base64 прямо внутри chat/completions**, в поле `input_audio`:

```json
{
  "messages": [{
    "role": "user",
    "content": [
      {"type": "text", "text": "ASR prompt"},
      {"type": "input_audio", "input_audio": {"data": "<base64>", "format": "ogg"}}
    ]
  }]
}
```

Это значит, что модель умеет слышать **и читать инструкцию одновременно**. Поэтому завёл отдельное поле **ASR prompt** для каждого бекенда — можно заранее рассказать модели про термины, имена и стиль.

Плюс:
— ✅ **Auto-fallback**: если основной провайдер лежит, код автоматом идёт OpenRouter → Groq → OpenAI (5 попыток)
— ✅ **OGG Vorbis по умолчанию** — аудио сжимается в 8-10 раз по сравнению с WAV без внешних зависимостей
— ✅ **Ноль секретов в коде** — ключи и endpoint'ы только в UI и локальном config.yaml (в .gitignore)

Репо: https://github.com/oiv-an/Voice

#buildinpublic #python #pyqt6 #openrouter #gemini

---

## Вариант 2 — развёрнутый (для Хабра / блога / LinkedIn)

### VoiceCapture v2.4.0 — добавил OpenRouter как третий ASR-бекенд

Апдейт моей портативной утилиты голосового ввода для Windows. До этого можно было распознавать речь через Groq или OpenAI Whisper. Теперь в список провайдеров добавлен **OpenRouter** с моделью `google/gemini-3.1-flash-lite-preview` по умолчанию.

#### Зачем ещё один бекенд

Groq — быстрый и бесплатный, но иногда лежит. OpenAI — стабильный, но дорогой. OpenRouter даёт доступ сразу к куче моделей по одному ключу, плюс хочется тестить мультимодальные модели Google и не только. Получилась хорошая возможность отказоустойчивости: если основной провайдер падает — автоматом подхватывает следующий.

#### Техническая особенность

Классический Whisper (и у Groq, и у OpenAI) работает через `POST /audio/transcriptions` с multipart-файлом — просто загружаешь WAV/MP3, получаешь текст. А вот мультимодальные модели типа Gemini работают иначе: аудио надо передать **в base64 прямо внутри стандартного chat/completions запроса**:

```python
payload = {
    "model": "google/gemini-3.1-flash-lite-preview",
    "modalities": ["text"],
    "messages": [{
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            {"type": "input_audio", "input_audio": {
                "data": base64.b64encode(audio_bytes).decode("ascii"),
                "format": "ogg"
            }}
        ]
    }],
    "stream": False
}
```

Это потребовало отдельного recognizer-класса, потому что протокол совсем не похож на Whisper. Зато открылась приятная фича — **ASR prompt**. Обычный Whisper принимает только короткий prompt-hint со словами для распознавания. А у мультимодальных моделей можно нормально объяснить задачу: *"распознавай техническую речь на русском, сохраняй английские термины в оригинале, не меняй стиль"*. Я добавил отдельное поле ASR prompt для каждого из трёх бекендов (для Whisper оно тоже работает как классический hint).

#### Проблема с размером и как её решил

Base64-кодирование раздувает файл на ~33%. Если брать WAV PCM_16 от 10-секундной записи — это ~320 КБ исходника + 427 КБ после base64. Жирновато для каждого запроса.

Решение — **OGG Vorbis через libsndfile**. Сжимает голос в 8-10 раз, libsndfile умеет это из коробки без внешних ffmpeg, работает прямо через `soundfile.write(..., format="OGG", subtype="VORBIS")`. Итого 10 секунд речи превращаются в 30-50 КБ. Пользователь в настройках может выбрать `ogg` / `mp3` / `wav`, но дефолт — `ogg` как оптимальный компромисс.

В коде сделал каскадный fallback по форматам: если запрошен mp3, а libsndfile не собран с mp3-поддержкой — автоматом падаем в ogg, если и ogg не удаётся — в wav. Никогда не ломается.

#### Fallback-каскад между бекендами

Пользователь в настройках выбирает основной бекенд (Groq / OpenAI / OpenRouter). Если он валится (таймаут, 404, 429) — код автоматом пробует остальные в порядке **OpenRouter → Groq → OpenAI**. Причём выбранный пользователем всегда ставится первым. До 5 попыток.

В проде это уже проверил — когда OpenRouter ответил 404 с Cloudflare-challenge, каскад автоматом перекинул запрос на Groq, пользователь даже не заметил сбоя. Вот пример из логов:

```
Trying recognition backend: openrouter
OpenRouter returned HTTP 404: <!DOCTYPE html>... Cloudflare challenge ...
Recognition error on backend openrouter
Trying recognition backend: groq
Recognition succeeded with backend: groq
```

#### Безопасность для open-source

Репозиторий публичный, поэтому критически важно не засветить ни ключи, ни endpoint'ы. Сделал так:
- всё вводится только через UI настроек
- сохраняется в локальный `config.yaml`, который уже в `.gitignore`
- в коде нет ни одного токена и ни одного захардкоженного URL
- даже дефолтный template config.yaml, который генерируется при первом запуске, имеет пустые `api_key` и `base_url`

Любой может форкнуть проект, поставить свои ключи в настройках — и всё работает.

#### Итого изменений v2.4.0

- 🧠 Третий ASR-бекенд — OpenRouter через chat/completions + base64 input_audio
- 🎙️ ASR prompt для каждого из трёх провайдеров
- 🔄 Каскадный fallback OpenRouter → Groq → OpenAI (до 5 попыток)
- 🗜️ OGG Vorbis по умолчанию для OpenRouter (8-10x компактнее WAV)
- 🔐 Ноль захардкоженных секретов

Код открыт: https://github.com/oiv-an/Voice

Пишу эту штуку для себя, но если кому-то зайдёт — буду рад звёздам и фидбеку.

#BuildInPublic #Python #PyQt6 #OpenRouter #Gemini #Whisper #VoiceInput

---

## Вариант 3 — твит-цепочка (X / Twitter)

**1/5** 🎙️ Добавил в свою open-source утилиту голосового ввода для Windows (VoiceCapture) третий бекенд распознавания — **OpenRouter с моделью google/gemini-3.1-flash-lite-preview**.

**2/5** Фишка в том, что OpenRouter не использует классический Whisper `/audio/transcriptions`. Там аудио летит в **base64 прямо внутри chat/completions**, в поле `input_audio`. Это значит — можно передать модели полноценный prompt параллельно со звуком.

**3/5** Поэтому добавил отдельное поле «ASR prompt» для каждого из трёх бекендов. Можно заранее объяснить модели: «распознавай техническую речь, сохраняй английские термины, не меняй стиль».

**4/5** Чтобы base64-раздутие не убивало скорость, сжимаю аудио в **OGG Vorbis через libsndfile** — в 8-10 раз компактнее WAV, без внешних ffmpeg-зависимостей. 10 секунд речи = 30-50 КБ.

**5/5** Плюс каскадный fallback: OpenRouter → Groq → OpenAI (до 5 попыток). Если основной провайдер лежит — пользователь даже не замечает сбоя.

Код открыт, секретов в репозитории ноль: https://github.com/oiv-an/Voice

#BuildInPublic #Python

---

## Примечание для публикации

- Все три варианта используются как шаблоны — выбирать по платформе
- Скриншоты: можно приложить окно настроек с OpenRouter секцией + выпадающий список audio format
- Gif: запись → распознавание → автовставка (демо-ролик 10-15 секунд)
