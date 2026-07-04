"""音声会話(Voice Chat)機能のメインロジック。

マイク入力 → Whisperで文字起こし → ローカルLLM(Ollama/Qwen)で応答生成
→ ローカルTTSでスピーカーに音声出力、というリアルタイム会話ループを
すべてネットワーク接続なしで実行する。

処理フロー(1ターンあたり):
  1. audio_io.record_until_enterでプッシュトゥトーク方式によりマイク音声を録音する
  2. Transcriberで録音データ(numpy配列)を直接文字起こしする
  3. 会話履歴に追記したうえでOllamaClient.chat_messagesに渡し、応答を生成する
  4. TTSSpeakerで応答テキストを読み上げる
"""
from __future__ import annotations

import threading

from rich.console import Console

from src.common.llm_client import OllamaClient
from src.common.persona import SHISUI_SYSTEM_PROMPT, VOICE_SYSTEM_PROMPT_ADDENDUM
from src.corpus import context as literary_context
from src.corpus.scheduler import maybe_run_daily_archive_crawl
from src.memory import context as memory_context
from src.memory import hippocampus
from src.memory.scheduler import maybe_run_daily_sleep
from src.minutes.transcriber import Transcriber
from src.study import report as study_report
from src.voicechat.audio_io import record_until_enter
from src.voicechat.tts import TTSSpeaker

DEFAULT_SYSTEM_PROMPT = SHISUI_SYSTEM_PROMPT + "\n" + VOICE_SYSTEM_PROMPT_ADDENDUM

EXIT_WORDS = {"終了", "おわり", "バイバイ", "exit", "quit"}

console = Console()


class VoiceChatAgent:
    """マイク⇔スピーカーでのリアルタイム音声対話を管理するエージェント。"""

    def __init__(
        self,
        transcriber: Transcriber | None = None,
        llm: OllamaClient | None = None,
        tts: TTSSpeaker | None = None,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    ) -> None:
        self.transcriber = transcriber or Transcriber()
        self.llm = llm or OllamaClient()
        self.tts = tts or TTSSpeaker()
        self.history: list[dict] = [{"role": "system", "content": system_prompt}]

    def listen(self) -> str:
        """マイクから1発話分を録音し、文字起こし結果を返す。"""
        audio = record_until_enter()
        if audio.size == 0:
            return ""
        segments = self.transcriber.transcribe(audio)
        return "".join(seg.text for seg in segments).strip()

    def respond(self, user_text: str) -> str:
        """会話履歴を保持したままLLMに問い合わせ、応答テキストを返す。"""
        self.history.append({"role": "user", "content": user_text})

        # 新皮質(長期記憶)・文学的感性コーパス・夜間修行レポートは、
        # self.historyを汚さないよう呼び出し時のみ差し込む
        unread_study_report = study_report.get_unread_report()
        extra_context_parts = [
            memory_context.build_recall_context(user_text),
            literary_context.build_literary_hint(user_text),
            unread_study_report,
        ]
        extra_context = "\n\n".join(part for part in extra_context_parts if part)

        if unread_study_report:
            study_report.mark_report_read()

        if extra_context:
            messages_for_call = (
                [self.history[0], {"role": "system", "content": extra_context}] + self.history[1:]
            )
        else:
            messages_for_call = self.history

        reply = self.llm.chat_messages(messages_for_call)
        self.history.append({"role": "assistant", "content": reply})

        # 海馬(短期記憶)にこのターンの発話を記録
        hippocampus.log_episode(role="user", content=user_text, source="voicechat")
        hippocampus.log_episode(role="assistant", content=reply, source="voicechat")

        return reply

    def run_turn(self) -> tuple[str, str] | None:
        """1往復分の対話(録音→応答→読み上げ)を実行する。無音の場合はNoneを返す。"""
        user_text = self.listen()
        if not user_text:
            return None
        reply = self.respond(user_text)
        self.tts.speak(reply)
        return user_text, reply

    def run_loop(self) -> None:
        """終了ワードが発話されるかCtrl+Cが押されるまで対話を繰り返す。"""
        # ネットワークI/Oやモデル呼び出しで数分かかることがあるため、会話開始をブロックしない
        threading.Thread(target=maybe_run_daily_sleep, daemon=True).start()
        threading.Thread(target=maybe_run_daily_archive_crawl, daemon=True).start()
        console.print(
            "[bold cyan]音声会話モードを開始します[/bold cyan]。"
            f"「{ '/'.join(sorted(EXIT_WORDS)) }」のいずれかを話すと終了します。(Ctrl+Cでも終了)"
        )
        try:
            while True:
                turn = self.run_turn()
                if turn is None:
                    console.print("[yellow](発話が認識できませんでした。もう一度お試しください)[/yellow]")
                    continue
                user_text, reply = turn
                console.print(f"[bold]あなた:[/bold] {user_text}")
                console.print(f"[bold green]AI:[/bold green] {reply}")
                if any(word in user_text for word in EXIT_WORDS):
                    console.print("[bold cyan]音声会話を終了します[/bold cyan]")
                    break
        except KeyboardInterrupt:
            console.print("\n[bold cyan]音声会話を終了します[/bold cyan]")
