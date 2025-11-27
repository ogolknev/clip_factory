#!/usr/bin/env python3
"""
Простой чистый скрипт для детекции сцен в видео и вывода временных отрезков сцен
в формате JSON, пригодных для публикации в YouTube Shorts.

Выходной формат:
{
  "scenes": [
    {"start": <number>, "end": <number>},
    ...
  ]
}

Принцип работы (минималистично):
- читаем видео через OpenCV
- выборочно (sampling_fps) берем кадры и считаем HSV-гистограммы
- считаем расстояние (Bhattacharyya) между соседними гистограммами
- если расстояние > threshold — считаем это границей сцены
- формируем сцены, фильтруем по min/max длине

Зависимости: opencv-python, numpy
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import List, Tuple

import cv2
import numpy as np


def get_video_props(video_capture: cv2.VideoCapture) -> Tuple[float, int]:
    frames_per_second = video_capture.get(cv2.CAP_PROP_FPS) or 0.0
    total_frames = int(video_capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    return frames_per_second, total_frames


def frame_timestamp(frame_index: int, frames_per_second: float) -> float:
    if frames_per_second <= 0:
        return 0.0
    return frame_index / frames_per_second


def histogram_for_frame(frame_image: np.ndarray) -> np.ndarray:
    hsv_image = cv2.cvtColor(frame_image, cv2.COLOR_BGR2HSV)
    # считаем 2D-гистограмму по H и S для более стабильного сравнения
    histogram = cv2.calcHist([hsv_image], [0, 1], None, [50, 60], [0, 180, 0, 256])
    cv2.normalize(histogram, histogram)
    return histogram


def detect_scene_boundaries(
    path: str,
    sampling_fps: float = 1.0,
    threshold: float = 0.6,
    max_samples: int | None = None,
) -> Tuple[List[float], float]:
    video_capture = cv2.VideoCapture(path)
    if not video_capture.isOpened():
        raise RuntimeError(f"Cannot open video: {path}")

    frames_per_second, total_frames = get_video_props(video_capture)
    duration_seconds = 0.0
    if frames_per_second > 0 and total_frames > 0:
        duration_seconds = total_frames / frames_per_second

    # если sampling_fps выше fps — берем каждый кадр
    frame_step = 1
    if sampling_fps > 0 and frames_per_second > 0:
        frame_step = max(1, int(round(frames_per_second / sampling_fps)))

    previous_histogram = None
    boundary_timestamps: List[float] = []
    frame_index = 0
    sampled_frames = 0

    while True:
        frame_read_success, frame_image = video_capture.read()
        if not frame_read_success:
            break

        if frame_index % frame_step == 0:
            sampled_frames += 1
            current_histogram = histogram_for_frame(frame_image)
            if previous_histogram is not None:
                # Bhattacharyya: 0 = identical, 1 = max distance
                distance = cv2.compareHist(previous_histogram, current_histogram, cv2.HISTCMP_BHATTACHARYYA)
                if distance >= threshold:
                    timestamp_seconds = frame_timestamp(frame_index, frames_per_second)
                    boundary_timestamps.append(timestamp_seconds)
            previous_histogram = current_histogram

            if max_samples is not None and sampled_frames >= max_samples:
                break

        frame_index += 1

    video_capture.release()
    return boundary_timestamps, duration_seconds


def build_scenes(boundary_timestamps: List[float], duration_seconds: float) -> List[Tuple[float, float]]:
    scenes: List[Tuple[float, float]] = []
    scene_start = 0.0
    for boundary_time in boundary_timestamps:
        # boundary time is where new scene starts -> end previous at boundary_time
        scene_end = boundary_time
        scenes.append((scene_start, scene_end))
        scene_start = boundary_time
    # final scene
    scenes.append((scene_start, duration_seconds or scene_start))
    return scenes


def filter_scenes(scenes: List[Tuple[float, float]], min_length_seconds: float, max_length_seconds: float) -> List[dict]:
    filtered = []
    for scene_start, scene_end in scenes:
        scene_length = scene_end - scene_start
        if scene_length <= 0:
            continue
        if scene_length < min_length_seconds:
            continue
        if max_length_seconds is not None and scene_length > max_length_seconds:
            continue
        filtered.append({"start": round(float(scene_start), 3), "end": round(float(scene_end), 3)})
    return filtered


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect scenes in a video and output JSON list of scenes.")
    parser.add_argument("input", help="Path to input video file")
    parser.add_argument("--sampling-fps", type=float, default=1.0, help="How many frames per second to sample (default: 1.0)")
    parser.add_argument("--threshold", type=float, default=0.6, help="Threshold for histogram distance (0..1), higher -> fewer cuts (default: 0.6)")
    parser.add_argument("--min-length", type=float, default=10.0, help="Minimum scene length in seconds to keep (default: 3)")
    parser.add_argument("--max-length", type=float, default=60.0, help="Maximum scene length in seconds to keep (default: 60)")
    parser.add_argument("--max-samples", type=int, default=None, help="Stop after this many sampled frames (for speed/testing)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        boundaries, duration = detect_scene_boundaries(
            args.input, sampling_fps=args.sampling_fps, threshold=args.threshold, max_samples=args.max_samples
        )
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 2

    scenes_raw = build_scenes(boundaries, duration)
    scenes = filter_scenes(scenes_raw, args.min_length, args.max_length)

    output = {"scenes": scenes}
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
