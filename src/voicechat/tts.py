"""pyttsx3によるローカルTTS(テキスト読み上げ)。

pyttsx3はOS標準の音声合成エンジン(macOS: NSSpeechSynthesizer / Windows: SAPI5 /
Linux: espeak)を利用するため、モデルのダウンロードが不要で即座に完全ローカルで動作する。
より自然な音声品質が必要な場合はMeloTTS等への差し替えを検討してよいが、
そちらはPyTorchベースの音声モデルを別途ダウンロードする必要があるため、
まずはセットアップが最も簡単なpyttsx3を既定エンジンとして採用している。
"""
from __future__ import annotations

import pyttsx3


class TTSSpeaker:
    """テキストを音声としてスピーカーから再生する。"""

    def __init__(self, rate: int = 175, voice_hint: str = "ja") -> None:
        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", rate)
        self._select_voice(voice_hint)

    def _select_voice(self, voice_hint: str) -> None:
        """日本語音声が見つかればそれを選択する(見つからない場合は既定の声のまま)。"""
        for voice in self.engine.getProperty("voices"):
            candidates = [voice.id or "", getattr(voice, "name", "") or ""]
            if any(voice_hint.lower() in c.lower() for c in candidates):
                self.engine.setProperty("voice", voice.id)
                return

    def speak(self, text: str) -> None:
        """テキストを読み上げる(再生完了までブロックする)。"""
        self.engine.say(text)
        self.engine.runAndWait()
