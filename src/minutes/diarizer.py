"""pyannote.audioによる話者分離(誰がいつ話したかの推定)。"""
from __future__ import annotations

from dataclasses import dataclass

from pyannote.audio import Pipeline

from config.settings import settings


@dataclass
class SpeakerSegment:
    start: float
    end: float
    speaker: str


class Diarizer:
    """pyannote.audioの話者分離パイプラインのラッパー。"""

    def __init__(self, hf_token: str | None = None) -> None:
        token = hf_token or settings.huggingface_token
        if not token:
            raise ValueError(
                "HUGGINGFACE_TOKENが設定されていません。.envファイルを確認してください。"
            )
        self.pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=token,
        )

    def diarize(self, audio_path: str) -> list[SpeakerSegment]:
        """音声ファイルを話者ごとの時間区間に分割する。"""
        diarization = self.pipeline(audio_path)
        return [
            SpeakerSegment(start=segment.start, end=segment.end, speaker=speaker)
            for segment, _track, speaker in diarization.itertracks(yield_label=True)
        ]
