#!/usr/bin/env python3
"""
Скрипт для нарезки видео на отдельные сцены по данным JSON.

Получает на вход:
1. Путь к видеофайлу
2. Путь к JSON файлу со сценами (формат: {"scenes": [{"start": <number>, "end": <number>}, ...]})

На выходе:
- Создает папку рядом с видеофайлом (название вроде "video_scenes")
- Сохраняет каждую сцену как отдельный видеофайл (scene_001.mp4, scene_002.mp4, и т.д.)

Требует: ffmpeg установленный в системе
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Dict


def load_scenes_from_json(json_path: str) -> List[Dict[str, float]]:
    """Читает JSON файл со сценами."""
    with open(json_path, "r", encoding="utf-8") as file:
        data = json.load(file)
    scenes = data.get("scenes", [])
    if not scenes:
        raise ValueError("No scenes found in JSON file")
    return scenes


def create_output_directory(video_path: str) -> str:
    """Создает папку для сохранения сцен рядом с видеофайлом."""
    video_file = Path(video_path)
    output_dir = video_file.parent / f"{video_file.stem}_scenes"
    output_dir.mkdir(exist_ok=True)
    return str(output_dir)


def extract_scene(
    video_path: str,
    start_seconds: float,
    end_seconds: float,
    output_path: str,
) -> None:
    """Вырезает сцену из видео используя ffmpeg."""
    duration_seconds = end_seconds - start_seconds
    command = [
        "ffmpeg",
        "-i", video_path,
        "-ss", str(start_seconds),
        "-t", str(duration_seconds),
        "-c:v", "copy",
        "-c:a", "copy",
        "-y",
        output_path,
    ]
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def extract_all_scenes(video_path: str, scenes: List[Dict[str, float]], output_dir: str) -> None:
    """Вырезает все сцены из видео."""
    for index, scene in enumerate(scenes, start=1):
        start_time = scene["start"]
        end_time = scene["end"]
        scene_duration = end_time - start_time

        output_filename = f"scene_{index:03d}.mp4"
        output_path = os.path.join(output_dir, output_filename)

        print(f"Extracting scene {index}: {start_time:.2f}s - {end_time:.2f}s ({scene_duration:.2f}s)...", end=" ")
        try:
            extract_scene(video_path, start_time, end_time, output_path)
            print(f"✓ saved to {output_filename}")
        except Exception as error:
            print(f"✗ failed: {error}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract scenes from video using JSON scene data.")
    parser.add_argument("video", help="Path to input video file")
    parser.add_argument("json_scenes", help="Path to JSON file with scenes")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # Проверяем существование файлов
    if not os.path.isfile(args.video):
        print(f"Error: Video file not found: {args.video}", file=sys.stderr)
        return 1

    if not os.path.isfile(args.json_scenes):
        print(f"Error: JSON file not found: {args.json_scenes}", file=sys.stderr)
        return 1

    try:
        scenes = load_scenes_from_json(args.json_scenes)
    except Exception as error:
        print(f"Error reading JSON: {error}", file=sys.stderr)
        return 1

    output_dir = create_output_directory(args.video)
    print(f"Output directory: {output_dir}")

    try:
        extract_all_scenes(args.video, scenes, output_dir)
        print(f"\n✓ Extracted {len(scenes)} scenes successfully")
        return 0
    except Exception as error:
        print(f"\nError: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
