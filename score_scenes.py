#!/usr/bin/env python3
"""
Скрипт скоринга интересности сцен на основе транскрипции.

Вход:
- JSON-файл с объектом: {"scenes": [{"start": <number>, "end": <number>, "segments": [...]}, ...]}

Выход:
- JSON объект с добавленными оценками интересности (0-100)
- Опция для фильтрации только топ-N самых интересных сцен

Методы скоринга:
1. simple (по умолчанию) — метрики текста: длина, плотность, ключевые слова
2. ai — анализ через OpenAI API (требует .env с OPENAI_API_KEY)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None  # type: ignore


def calculate_scene_score(segments: list[dict]) -> int:
    """Вычисляет оценку интересности сцены (0-100) на основе сегментов."""
    if not segments:
        return 0

    total_text_length = sum(len(seg.get("text", "").strip()) for seg in segments)
    total_duration = sum(seg.get("end", 0) - seg.get("start", 0) for seg in segments)
    text_count = sum(len(seg.get("text", "").split()) for seg in segments)

    # Базовый скор: длина текста (макс 30 баллов)
    length_score = min(30, total_text_length / 10)

    # Скор за плотность слов (макс 30 баллов)
    density_score = 0
    if total_duration > 0:
        words_per_second = text_count / total_duration
        density_score = min(30, words_per_second * 5)

    # Скор за интерес (макс 40 баллов)
    interest_score = 0
    full_text = " ".join(seg.get("text", "") for seg in segments).lower()

    # Пунктуация
    if "?" in full_text:
        interest_score += 10
    if "!" in full_text:
        interest_score += 10

    # Ключевые слова (простой список)
    keywords = ["важно", "значит", "потому", "поэтому", "следовательно",
                "например", "результат", "вывод", "интересно", "необычно",
                "главное", "ключевой"]
    keyword_count = sum(full_text.count(kw) for kw in keywords)
    interest_score += min(20, keyword_count * 3)

    total_score = length_score + density_score + interest_score
    return round(min(100, total_score))


def load_scenes_with_transcription(json_path: str) -> dict:
    """Загружает JSON с сценами и транскрипцией."""
    with open(json_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data


def score_scene_with_ai(segments: list[dict], client: any) -> int:
    """Получает оценку интересности от OpenAI API."""
    if not segments:
        return 0

    text = " ".join(seg.get("text", "").strip() for seg in segments)
    if not text:
        return 0

    try:
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
            messages=[
                {
                    "role": "system",
                    "content": "Ты оцениваешь интересность контента от 0 до 100. Возвращай только число без объяснений."
                },
                {
                    "role": "user",
                    "content": f"Оцени интересность этого текста (0-100):\n\n{text}"
                }
            ],
            temperature=0.3,
            max_tokens=10
        )
        score_text = response.choices[0].message.content.strip()
        score = int(score_text.split()[0])
        return max(0, min(100, score))
    except (ValueError, IndexError):
        return 0
    except Exception as error:
        print(f"Warning: AI scoring failed: {error}", file=sys.stderr)
        return 0


def init_openai_client() -> any:
    """Инициализирует OpenAI клиент."""
    if load_dotenv:
        load_dotenv()

    if OpenAI is None:
        raise RuntimeError(
            "OpenAI package is not installed. Install with: pip install openai python-dotenv")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY not found in .env file. Please set it and try again.")

    api_base = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
    return OpenAI(api_key=api_key, base_url=api_base)


def score_scenes(data: dict, top_n: int | None = None) -> dict:
    """Добавляет оценки интересности к сценам и фильтрует топ-N."""
    scenes = data.get("scenes", [])

    # Добавляем скоры к каждой сцене
    for scene in scenes:
        segments = scene.get("segments", [])
        scene["score"] = calculate_scene_score(segments)

    # Сортируем по скору (убывание)
    scenes_sorted = sorted(scenes, key=lambda s: s["score"], reverse=True)

    # Если нужно, берём только топ-N
    if top_n is not None:
        scenes_sorted = scenes_sorted[:top_n]
        # Восстанавливаем оригинальный порядок по времени
        scenes_sorted = sorted(scenes_sorted, key=lambda s: s["start"])

    return {"scenes": scenes_sorted}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Score scenes by interest based on transcription.")
    parser.add_argument("json_file", help="Path to JSON file with scenes and transcription")
    parser.add_argument("--top", type=int, default=10,
                        help="Keep only top N most interesting scenes (default: 10)")
    parser.add_argument("--all", action="store_true",
                        help="Keep all scenes without filtering")
    parser.add_argument("--use-ai", action="store_true",
                        help="Use OpenAI API for scoring (requires .env with OPENAI_API_KEY)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not sys.stdin.isatty():
        # Если данные поступают через stdin
        data = json.load(sys.stdin)
    else:
        # Иначе читаем из файла
        try:
            data = load_scenes_with_transcription(args.json_file)
        except FileNotFoundError:
            print(f"Error: file not found: {args.json_file}", file=sys.stderr)
            return 2
        except json.JSONDecodeError as error:
            print(f"Error: invalid JSON: {error}", file=sys.stderr)
            return 2

    try:
        # Если используется AI скоринг
        if args.use_ai:
            client = init_openai_client()
            scenes = data.get("scenes", [])
            print("Scoring scenes with AI...", file=sys.stderr)
            for idx, scene in enumerate(scenes, start=1):
                segments = scene.get("segments", [])
                score = score_scene_with_ai(segments, client)
                scene["score"] = score
                print(f"Scene {idx}: {score}", file=sys.stderr)
        else:
            # Используем простой скоринг
            for scene in data.get("scenes", []):
                segments = scene.get("segments", [])
                scene["score"] = calculate_scene_score(segments)

        # Сортируем и фильтруем
        top_n = None if args.all else args.top
        result = score_scenes(data, top_n=top_n)
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        return 3

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
