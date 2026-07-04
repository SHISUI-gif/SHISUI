"""議事録作成機能のメインロジック。

faster-whisperによる文字起こしと、pyannote.audioによる話者分離を組み合わせ、
「誰が・いつ・何を話したか」を復元したうえで、ローカルLLMによる要約を行う。
すべての処理はネットワーク接続なしで完結する(初回のモデルダウンロードを除く)。

処理フロー:
  1. Transcriberで音声全体をセグメント単位で文字起こしする
  2. Diarizerで話者ごとの発話区間を推定する
  3. 発話区間の重なりが最大のセグメントを採用し、各文字起こしセグメントに話者ラベルを付与する
  4. 話者ラベル付き文字起こしをMinutesSummarizerに渡し、議事録サマリーを生成する
  5. 文字起こし全文 + サマリーをMarkdownとして output/minutes/ 配下に保存する
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from config.settings import MINUTES_DIR
from src.minutes.diarizer import Diarizer, SpeakerSegment
from src.minutes.summarizer import MinutesSummarizer
from src.minutes.transcriber import Transcriber, TranscriptSegment


def _assign_speaker(segment: TranscriptSegment, speaker_segments: list[SpeakerSegment]) -> str:
    """文字起こしセグメントと最も重なりが大きい話者セグメントのラベルを返す。"""
    best_speaker = "不明"
    best_overlap = 0.0
    for spk in speaker_segments:
        overlap = min(segment.end, spk.end) - max(segment.start, spk.start)
        if overlap > best_overlap:
            best_overlap = overlap
            best_speaker = spk.speaker
    return best_speaker


def _format_timestamp(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


class MinutesAgent:
    """音声ファイルから話者分離付き議事録を生成するエージェント。"""

    def __init__(
        self,
        transcriber: Transcriber | None = None,
        diarizer: Diarizer | None = None,
        summarizer: MinutesSummarizer | None = None,
    ) -> None:
        self.transcriber = transcriber or Transcriber()
        self.diarizer = diarizer or Diarizer()
        self.summarizer = summarizer or MinutesSummarizer()

    def _build_labeled_transcript(
        self, segments: list[TranscriptSegment], speaker_segments: list[SpeakerSegment]
    ) -> str:
        lines = []
        for seg in segments:
            speaker = _assign_speaker(seg, speaker_segments)
            lines.append(f"[{_format_timestamp(seg.start)}] {speaker}: {seg.text}")
        return "\n".join(lines)

    def run(self, audio_path: str) -> Path:
        """音声ファイルから議事録Markdownを生成し、保存先パスを返す。"""
        segments = self.transcriber.transcribe(audio_path)
        speaker_segments = self.diarizer.diarize(audio_path)
        labeled_transcript = self._build_labeled_transcript(segments, speaker_segments)
        summary = self.summarizer.summarize(labeled_transcript)

        audio_name = Path(audio_path).stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = MINUTES_DIR / f"{timestamp}_{audio_name}.md"

        content = (
            f"# 議事録: {audio_name}\n\n"
            f"{summary}\n\n"
            "## 話者別 文字起こし全文\n\n"
            f"{labeled_transcript}\n"
        )
        output_path.write_text(content, encoding="utf-8")
        return output_path
