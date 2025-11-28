# Scene Analysis Pipeline

Полный пайплайн для анализа видео: разделение на сцены, транскрипция и скоринг интересности.

## Установка

```fish
python -m venv venv
source ./venv/bin/activate.fish
pip install -r requirements.txt
```

**Системные зависимости:**
- `ffmpeg` — для работы с видео и аудио

```fish
# Arch/CachyOS
sudo pacman -S ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg
```

Проверьте установку:
```fish
ffmpeg -version
```

## Скрипты

### 1. scene_splitter.py — Детекция сцен по визуальному контенту

Разделяет видеофайл на сцены на основе анализа кадров (сравнение гистограмм).

**Использование:**
```fish
python scene_splitter.py /path/to/video.mp4 [OPTIONS]
```

**Параметры:**
- `--sampling-fps` — сколько кадров/сек для анализа (по умолчанию: 1)
- `--threshold` — порог расстояния гистограмм (0..1), чем выше — тем меньше разрезов (по умолчанию: 0.6)
- `--min-length` — минимальная длина сцены в секундах (по умолчанию: 3)
- `--max-length` — максимальная длина сцены в секундах (по умолчанию: 60)

**Пример:**
```fish
python scene_splitter.py video.mp4 --sampling-fps 1 --threshold 0.6 --min-length 3 --max-length 60
```

**Выход:**
JSON файл со списком сцен в формате:
```json
{
  "scenes": [
    {"start": 0.0, "end": 12.345},
    {"start": 12.345, "end": 45.67}
  ]
}
```

---

### 2. extract_scenes.py — Экспорт сцен в отдельные файлы

Нарезает видео по полученным сценам и сохраняет каждую в отдельный файл для проверки.

**Использование:**
```fish
python extract_scenes.py /path/to/video.mp4 scenes.json
```

**Выход:**
Создаёт папку `video_scenes/` рядом с видеофайлом с файлами:
- `scene_001.mp4`
- `scene_002.mp4`
- и т.д.

---

### 3. transcribe_scenes.py — Транскрипция сцен

Извлекает аудио из видео по сценам и транскрибирует их через Whisper.

**Использование:**
```fish
python transcribe_scenes.py /path/to/video.mp4 scenes.json [OPTIONS]
```

**Параметры:**
- `--model` — Whisper модель (tiny, base, small, medium, large; по умолчанию: small)
- `--language` — код языка для транскрипции (e.g., ru, en; опционально, авто-определение)

**Примеры:**
```fish
# Транскрипция на англ. с моделью small
python transcribe_scenes.py video.mp4 scenes.json --model small --language en

# Транскрипция с авто-определением языка
python transcribe_scenes.py video.mp4 scenes.json
```

**Выход:**
JSON объект с транскрипциями:
```json
{
  "scenes": [
    {
      "start": 0.0,
      "end": 12.345,
      "segments": [
        {
          "start": 0.5,
          "end": 5.2,
          "text": "Hello world"
        }
      ]
    }
  ]
}
```

**Примечание:** Первый запуск скачает модель Whisper (~2-3 GB в зависимости от размера).

---

### 4. score_scenes.py — Скоринг интересности сцен

Оценивает интересность каждой сцены и фильтрует топ-N сцен.

**Использование:**
```fish
python score_scenes.py transcribed.json [OPTIONS]
```

**Параметры:**
- `--top N` — оставить только N самых интересных сцен (по умолчанию: 10)
- `--all` — сохранить все сцены без фильтрации
- `--use-ai` — использовать AI-скоринг через OpenAI API (требует .env)

**Методы скоринга:**

#### Простой скоринг (по умолчанию)
Основан на текстовых метриках:
- Длина текста (макс 30 баллов)
- Плотность слов (слов в секунду) (макс 30 баллов)
- Маркеры интереса: вопросы, восклицания, ключевые слова (макс 40 баллов)

```fish
python score_scenes.py transcribed.json --top 10
```

#### AI-скоринг через OpenAI API
Анализирует текст с помощью GPT для более качественной оценки интересности.

**Настройка:**
1. Скопируйте `.env.example` в `.env`:
```fish
cp .env.example .env
```

2. Отредактируйте `.env` и добавьте ваши данные:
```
OPENAI_API_KEY=sk-...
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_MODEL=gpt-3.5-turbo
```

3. Запустите с флагом `--use-ai`:
```fish
python score_scenes.py transcribed.json --top 10 --use-ai
```

**Примеры:**
```fish
# Топ 5 интересных сцен, простой скоринг
python score_scenes.py transcribed.json --top 5

# Все сцены с оценками
python score_scenes.py transcribed.json --all

# Топ 20 сцен с AI-скорингом
python score_scenes.py transcribed.json --top 20 --use-ai
```

**Выход:**
JSON объект с добавленными оценками интересности:
```json
{
  "scenes": [
    {
      "start": 5.2,
      "end": 15.7,
      "score": 85,
      "segments": [...]
    }
  ]
}
```

---

## Полный пайплайн (пример)

```fish
# 1. Детекция сцен
python scene_splitter.py video.mp4 --threshold 0.6 > scenes.json

# 2. Опционально: проверьте результат
python extract_scenes.py video.mp4 scenes.json

# 3. Транскрипция всех сцен
python transcribe_scenes.py video.mp4 scenes.json --language ru > transcribed.json

# 4. Скоринг и фильтрация топ-10 интересных сцен
python score_scenes.py transcribed.json --top 10 > top_scenes.json

# 5. Если нужен более качественный анализ, используйте AI
python score_scenes.py transcribed.json --top 10 --use-ai > top_scenes_ai.json
```

---

## Заметки

- **Производительность:** Для больших видео можно использовать меньше сцен или другие параметры `--sampling-fps`
- **Языки:** Whisper поддерживает 99+ языков, автоматически определяет язык если не указан
- **Модели Whisper:** tiny (~39M) — fastest, large (~3B) — most accurate
- **OpenAI API:** Ключ получите на https://platform.openai.com/api-keys
- **Стоимость API:** ~0.002 USD за сцену при использовании gpt-3.5-turbo

---

## Требования

Смотрите `requirements.txt`:
- `opencv-python` — анализ видео и гистограмм
- `numpy` — числовые вычисления
- `openai-whisper` — транскрипция аудио
- `openai` — AI скоринг (опционально)
- `python-dotenv` — загрузка конфигурации из .env
