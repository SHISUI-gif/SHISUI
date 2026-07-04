"""faster-whisperによる音声の文字起こし(完全ローカル実行)。"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from faster_whisper import WhisperModel

from config.settings import settings


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str


class Transcriber:
    """faster-whisperを使い、音声ファイルをセグメント単位で文字起こしする。"""

    def __init__(self, model_size: str | None = None, device: str | None = None) -> None:
        self.model = WhisperModel(
            model_size or settings.whisper_model_size,
            device=device or settings.whisper_device,
            compute_type="int8" if (device or settings.whisper_device) == "cpu" else "float16",
        )

    def transcribe(self, audio: str | np.ndarray, language: str = "ja") -> list[TranscriptSegment]:
        """音声を文字起こしし、タイムスタンプ付きセグメントのリストを返す。

        audioには音声ファイルパスのほか、マイク録音などで得た16kHzモノラルの
        float32 numpy配列を直接渡すこともできる(音声会話モジュールで利用)。
        """
        segments, _info = self.model.transcribe(audio, language=language, vad_filter=True)
        return [
            TranscriptSegment(start=seg.start, end=seg.end, text=seg.text.strip())
            for seg in segments
        ]
