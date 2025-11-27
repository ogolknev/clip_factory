# Scene splitter

Простой скрипт для деления видео на сцены и вывода списка сцен в JSON-формате.

Установка зависимостей:

```fish
python -m venv venv
source ./venv/bin/activate.fish
pip install -r requirements.txt
```

## scene_splitter.py: Детекция сцен

Пример использования:

```fish
python scene_splitter.py /path/to/video.mp4 --sampling-fps 1 --threshold 0.6 --min-length 3 --max-length 60
```

Параметры:
- `--sampling-fps` — сколько кадров/сек для анализа (по умолчанию 1)
- `--threshold` — порог расстояния гистограмм (0..1), чем выше — тем меньше разрезов
- `--min-length` — минимальная длина сцены в секундах (по умолчанию 3)
- `--max-length` — максимальная длина сцены в секундах (по умолчанию 60)

Формат вывода:

```json
{
  "scenes": [
    {"start": 0.0, "end": 12.345},
    {"start": 12.345, "end": 45.67}
  ]
}
```

Примечание: скрипт минималистичный и не учитывает все возможные пограничные случаи. Для лучшей точности можно увеличить `sampling-fps` или применять аудио- или более сложные видео-метрики.

## extract_scenes.py: Проверка результатов

Для проверки работы детекции используйте вспомогательный скрипт, который нарезает видео по полученным JSON данным:

```fish
python extract_scenes.py /path/to/video.mp4 scenes.json
```

Скрипт создаст папку рядом с видеофайлом (например, `video_scenes/`) и сохранит каждую сцену как отдельный файл (`scene_001.mp4`, `scene_002.mp4` и т.д.).

**Требование:** `ffmpeg` должен быть установлен в системе. Установите:

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
