#!/usr/bin/env python3
"""
Простой скрипт для транскрипции сцен видеофайла.

Вход:
- путь к видеофайлу
- путь к JSON-файлу со сценами (формат: {"scenes": [{"start": <number>, "end": <number>}, ...]})

Выход:
- печатает в stdout JSON объект: {"scenes": [{"start":..,"end":..,"transcription": "..."}, ...]}

Зависимости: `openai-whisper` (pip package), `ffmpeg` в системе

Принцип работы:
- читает список сцен
- для каждой сцены вырезает аудио-фрагмент через ffmpeg во временный файл
- передаёт аудио в Whisper и получает текст транскрипции
- выводит результирующий JSON

Код максимально простой и понятный; опции модели и языка доступны через CLI.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from typing import Any

try:
    import whisper
except ImportError:  # pragma: no cover - user may not have package installed
    whisper = None  # type: ignore


def load_scenes(json_path: str) -> list[dict[str, float]]:
    with open(json_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    scenes = data.get("scenes", [])
    if not isinstance(scenes, list):
        raise ValueError("Invalid scenes JSON: 'scenes' should be a list")
    return scenes


def extract_audio_segment(video_path: str, start: float, end: float, output_path: str) -> None:
    """Вырезает аудио-фрагмент из видео с помощью ffmpeg в wav формат."""
    duration = max(0.0, end - start)
    command = [
        "ffmpeg",
        "-ss",
        str(start),
        "-i",
        video_path,
        "-t",
        str(duration),
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        "-y",
        output_path,
    ]
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)


def transcribe_segment(model: Any, audio_path: str, language: str | None = None) -> dict[str, Any]:
    """Запускает модель Whisper и возвращает результаты транскрипции.

    Возвращает словарь с ключами:
    - 'text' : объединённый текст
    - 'segments' : список сегментов с полями 'start', 'end', 'text' (в секундах, относительных к аудиофайлу)
    """
    kwargs = {"language": language} if language else {}
    result = model.transcribe(audio_path, **kwargs)
    text = result.get("text", "")
    segments = result.get("segments", [])
    return {"text": text.strip(), "segments": segments}


def transcribe_scenes(
    video_path: str,
    scenes_json: str,
    model_name: str = "small",
    language: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    if whisper is None:
        raise RuntimeError(
            "Whisper package is not installed. Install with: pip install openai-whisper")

    scenes = load_scenes(scenes_json)
    model = whisper.load_model(model_name)

    output_scenes: list[dict[str, Any]] = []

    for idx, scene in enumerate(scenes, start=1):
        start = float(scene.get("start", 0.0))
        end = float(scene.get("end", start))

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            print(
                f"Transcribing scene {idx}: {start:.2f}s - {end:.2f}s...", file=sys.stderr)
            extract_audio_segment(video_path, start, end, tmp_path)
            trans_result = transcribe_segment(
                model, tmp_path, language=language)

            # segments from Whisper are relative to the audio file (scene).
            # Мы сохраняем их относительными к началу сцены (подходят для локального SRT внутри сцены).
            relative_segments: list[dict[str, Any]] = []
            for seg in trans_result.get("segments", []):
                rel_start = float(seg.get("start", 0.0))
                rel_end = float(seg.get("end", rel_start))
                seg_text = seg.get("text", "").strip()
                relative_segments.append(
                    {"start": round(rel_start, 3), "end": round(rel_end, 3), "text": seg_text})

            # Сохраняем только сегменты (относительные ко времени начала сцены)
            output_scenes.append(
                {
                    "start": round(start, 3),
                    "end": round(end, 3),
                    "segments": relative_segments,
                }
            )
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass

    return {"scenes": output_scenes}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Transcribe scenes from a video using Whisper.")
    parser.add_argument("video", help="Path to input video file")
    parser.add_argument("scenes_json", help="Path to JSON file with scenes")
    parser.add_argument("--model", default="small",
                        help="Whisper model to use (tiny, base, small, medium, large)")
    parser.add_argument("--language", default=None,
                        help="Optional language code to force (e.g., en, ru)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not os.path.isfile(args.video):
        print(f"Error: video file not found: {args.video}", file=sys.stderr)
        return 2
    if not os.path.isfile(args.scenes_json):
        print(
            f"Error: scenes JSON file not found: {args.scenes_json}", file=sys.stderr)
        return 2

    try:
        result = transcribe_scenes(
            args.video, args.scenes_json, model_name=args.model, language=args.language)
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        return 3

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
