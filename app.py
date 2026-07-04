#!/usr/bin/env python3
"""ローカルAIツールのCLIエントリポイント。

サブコマンド:
  research   : テーマを指定して自律リサーチを実行し、Markdownレポートを生成する
  minutes    : 音声ファイルを指定して話者分離付き議事録を生成する
  voicechat  : マイクとスピーカーでリアルタイム音声会話を行う
  debate     : 3つのAIエージェントに討論させ、結論レポートを生成する(フィードバック学習付き)
  memory     : 志粋の記憶圧縮システム(海馬→睡眠モード→新皮質)を手動操作する
  corpus     : 志粋の文学的感性コーパス(青空文庫)を手動操作する
  study      : 志粋の「夜間修行」(メンターAIとの自律学習)を手動操作する
  api        : 志粋の頭脳をHTTP API(FastAPI)として起動する(将来のNext.jsフロントエンド向け)
  debate-autonomous : 志粋が自分の弱点トピックについて自律的に討論する(夜間修行とは別ジョブ)
  evolution  : 自己修復プロトコル(エラー検知→修正案生成→人間承認)を操作する
"""
from __future__ import annotations

import argparse
import sys

from rich.console import Console

console = Console()


def run_research(topic: str, max_results: int) -> int:
    from src.research.report_generator import ResearchAgent

    console.print(f"[bold cyan]自律リサーチを開始します[/bold cyan]: テーマ = {topic}")
    agent = ResearchAgent()
    output_path = agent.run(topic, max_results_per_query=max_results)
    console.print(f"[bold green]レポートを生成しました[/bold green]: {output_path}")
    return 0


def run_minutes(audio_path: str) -> int:
    from src.minutes.minutes_generator import MinutesAgent

    console.print(f"[bold cyan]議事録作成を開始します[/bold cyan]: 音声ファイル = {audio_path}")
    agent = MinutesAgent()
    output_path = agent.run(audio_path)
    console.print(f"[bold green]議事録を生成しました[/bold green]: {output_path}")
    return 0


def run_voicechat() -> int:
    from src.voicechat.voice_chat_agent import VoiceChatAgent

    agent = VoiceChatAgent()
    agent.run_loop()
    return 0


def run_debate(topic: str, rounds: int, skip_feedback: bool) -> int:
    from src.debate.debate_agent import DebateSystem, collect_feedback

    console.print(f"[bold cyan]マルチエージェント討論を開始します[/bold cyan]: テーマ = {topic}")
    system = DebateSystem(max_rounds=rounds)
    result = system.run(topic)

    console.print(f"[bold green]討論レポートを生成しました[/bold green]: {result.report_path}")
    console.print("\n[bold]== 結論 ==[/bold]")
    console.print(result.conclusion)

    if not skip_feedback:
        collect_feedback(topic, result.conclusion)
    return 0


def run_memory_sleep() -> int:
    from src.memory.sleep import run_sleep_cycle

    console.print("[bold cyan]睡眠モードを実行します[/bold cyan]: 海馬 → 新皮質への記憶圧縮")
    result = run_sleep_cycle()
    console.print(
        f"[bold green]完了[/bold green]: エピソード{result.episodes_considered}件を検討、"
        f"新規/更新メモリ{result.memories_added}件(うちsupersede{result.memories_superseded}件)"
    )
    return 0


def run_memory_list() -> int:
    from src.memory import neocortex

    memories = neocortex.list_all()
    if not memories:
        console.print("[yellow]新皮質にはまだ記憶がありません。[/yellow]")
        return 0

    for m in memories:
        console.print(f"[dim]{m.timestamp}[/dim] [bold]\\[{m.category}][/bold] {m.text}")
    return 0


def run_corpus_ingest(force: bool) -> int:
    from src.corpus.ingest import run_ingest

    console.print("[bold cyan]文学的感性コーパスの取り込みを開始します[/bold cyan](青空文庫・厳選作品)")
    result = run_ingest(force=force)
    console.print(f"[bold green]完了[/bold green]: {result.succeeded}件取り込み")
    if result.skipped:
        console.print(f"[yellow]スキップ: {len(result.skipped)}件[/yellow]")
        for item in result.skipped:
            console.print(f"  - {item}")
    if result.failed:
        console.print(f"[red]失敗: {len(result.failed)}件[/red]")
        for item in result.failed:
            console.print(f"  - {item}")
    return 0


def run_corpus_list() -> int:
    from src.corpus import ingest

    hints = ingest.list_all()
    if not hints:
        console.print("[yellow]文学的感性コーパスにはまだ何も取り込まれていません。[/yellow]")
        return 0

    for hint in hints:
        console.print(f"[bold]\\[{hint.author}『{hint.title}』][/bold] {hint.descriptor}")
    return 0


def run_corpus_archive_crawl() -> int:
    from src.corpus.full_archive import run_daily_archive_crawl

    console.print("[bold cyan]青空文庫全体クロールを実行します[/bold cyan](本日分)")
    result = run_daily_archive_crawl()

    if result.complete:
        console.print(f"[bold green]全作品の取り込みが完了しました[/bold green](累計{result.total_ingested}件)")
    else:
        console.print(
            f"[bold green]完了[/bold green]: 本日{result.ingested_this_run}件取り込み"
            f"(累計{result.total_ingested}件、現在の作家: {result.current_author})"
        )
    if result.errors:
        console.print(f"[yellow]エラー: {len(result.errors)}件[/yellow]")
        for item in result.errors:
            console.print(f"  - {item}")
    return 0


def run_corpus_archive_status() -> int:
    from src.corpus.full_archive import get_progress_summary

    summary = get_progress_summary()
    if summary["total_authors"] == 0:
        console.print("[yellow]まだクロールを開始していません(初回は作家一覧の取得から始まります)。[/yellow]")
        return 0

    console.print(f"[bold]青空文庫全体クロールの進捗[/bold]")
    console.print(f"  作家: {summary['author_cursor']} / {summary['total_authors']}")
    console.print(f"  累計取り込み作品数: {summary['total_ingested']}")
    console.print(f"  完了: {'はい' if summary['complete'] else 'いいえ'}")
    return 0


def run_study_run() -> int:
    from src.study.study_session import run_study_session

    console.print("[bold cyan]夜間修行を開始します[/bold cyan](弱点分析 → メンターAIとの討論 → 記憶への統合)")
    result = run_study_session()

    if result.skipped:
        console.print("[yellow]学ぶべき弱点が見つからなかったため、今回はスキップしました。[/yellow]")
        return 0

    console.print(
        f"[bold green]完了[/bold green]: {len(result.topics_studied)}トピックを学習、"
        f"Gemini呼び出し{result.gemini_calls}回"
    )
    for topic_result in result.topics_studied:
        console.print(f"  [bold]\\[{topic_result.topic}][/bold] {topic_result.insight}")
    return 0


def run_study_report() -> int:
    from src.study import report

    session = report.get_latest_session()
    if session is None:
        console.print("[yellow]まだ夜間修行の記録がありません。[/yellow]")
        return 0

    console.print(f"[bold]直近の夜間修行[/bold]: {session['timestamp']}")
    for topic in session.get("topics", []):
        console.print(f"  [bold]\\[{topic['topic']}][/bold] {topic['insight']}")
    return 0


def run_api(port: int) -> int:
    import uvicorn

    # 0.0.0.0で待ち受けることで、同じWi-Fi上のスマホ等からNext.jsフロントエンド
    # 経由でアクセスした際にも、そのフロントエンドから見えるAPIとして機能する
    console.print(f"[bold cyan]志粋のAPIサーバーを起動します[/bold cyan]: http://0.0.0.0:{port}")
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=port)
    return 0


def run_debate_autonomous() -> int:
    from src.debate.autonomous import run_autonomous_debate

    console.print("[bold cyan]自律討論を開始します[/bold cyan](弱点分析 → 3エージェントで討論 → 記憶への統合)")
    result = run_autonomous_debate()

    if result.skipped:
        console.print("[yellow]討論すべき弱点が見つからなかったため、今回はスキップしました。[/yellow]")
        return 0

    console.print(f"[bold green]完了[/bold green]: {len(result.topics_debated)}トピックを討論")
    for debated in result.topics_debated:
        console.print(f"  [bold]\\[{debated.topic}][/bold] {debated.conclusion_summary}")
        console.print(f"    レポート: {debated.report_path}")
    return 0


def run_evolution_scan() -> int:
    from src.core.evolution import generate_fix_proposals

    console.print("[bold cyan]自己修復プロトコル[/bold cyan]: 未レビューのエラーを確認し、修正案を生成します")
    proposals = generate_fix_proposals()

    if not proposals:
        console.print("[yellow]新しい修正案はありませんでした。[/yellow]")
        return 0

    console.print(f"[bold green]完了[/bold green]: {len(proposals)}件の修正案を生成しました")
    for proposal in proposals:
        console.print(f"  [bold]\\[{proposal.id}][/bold] {proposal.file_path} — {proposal.explanation[:60]}")
    console.print("`python app.py evolution show <id>` で内容を確認できます。")
    return 0


def run_evolution_list() -> int:
    from src.core.evolution import list_pending_proposals

    proposals = list_pending_proposals()
    if not proposals:
        console.print("[yellow]承認待ちの修正案はありません。[/yellow]")
        return 0

    for proposal in proposals:
        console.print(f"[bold]\\[{proposal['id']}][/bold] {proposal['file_path']}")
        console.print(f"  {proposal['explanation']}")
    return 0


def run_evolution_feedback_list() -> int:
    from src.core.feedback_log import get_unreviewed_feedback

    feedback = get_unreviewed_feedback()
    if not feedback:
        console.print("[yellow]未レビューの訂正・不満はありません。[/yellow]")
        return 0

    console.print(
        "[dim]例外は起きていないが、会話中にユーザーから訂正・不満が伝えられた履歴です。"
        "実際にコードの問題か、単なる会話の行き違いかは人間の目で判断してください。[/dim]\n"
    )
    for entry in feedback:
        console.print(f"[bold]\\[{entry['id']}][/bold] {entry['timestamp']}")
        console.print(f"  質問: {entry['previous_user_message']}")
        console.print(f"  志粋: {entry['previous_assistant_response']}")
        console.print(f"  訂正: [red]{entry['correction_message']}[/red]\n")
    console.print(
        "`python app.py evolution feedback-dismiss <id>` でレビュー済みにできます。"
    )
    return 0


def run_evolution_feedback_dismiss(feedback_id: str) -> int:
    from src.core.feedback_log import mark_reviewed

    mark_reviewed(feedback_id)
    console.print(f"[dim]{feedback_id} をレビュー済みにしました。[/dim]")
    return 0


def run_evolution_show(proposal_id: str) -> int:
    from src.core.evolution import get_proposal

    proposal = get_proposal(proposal_id)
    if proposal is None:
        console.print(f"[bold red]修正案 {proposal_id} が見つかりません。[/bold red]")
        return 1

    console.print(f"[bold]ファイル[/bold]: {proposal['file_path']}")
    console.print(f"[bold]説明[/bold]: {proposal['explanation']}")
    console.print(proposal["diff"])
    return 0


def run_evolution_apply(proposal_id: str) -> int:
    from src.core.evolution import apply_proposal

    ok, message = apply_proposal(proposal_id)
    style = "bold green" if ok else "bold red"
    console.print(f"[{style}]{message}[/{style}]")
    return 0 if ok else 1


def run_evolution_reject(proposal_id: str) -> int:
    from src.core.evolution import reject_proposal

    if reject_proposal(proposal_id):
        console.print(f"[yellow]修正案 {proposal_id} を却下しました。[/yellow]")
        return 0
    console.print(f"[bold red]修正案 {proposal_id} が見つかりません。[/bold red]")
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="app.py",
        description="ローカルAIツール: 自律リサーチ / 議事録作成 / 音声会話 / マルチエージェント討論",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    research_parser = subparsers.add_parser("research", help="自律リサーチレポートを生成する")
    research_parser.add_argument("topic", help="調査したいテーマ")
    research_parser.add_argument(
        "--max-results", type=int, default=5, help="サブクエリごとの検索結果取得件数(既定: 5)"
    )

    minutes_parser = subparsers.add_parser("minutes", help="音声から議事録を生成する")
    minutes_parser.add_argument("audio_path", help="議事録化したい音声ファイルのパス")

    subparsers.add_parser("voicechat", help="マイクとスピーカーでリアルタイム音声会話を行う")

    debate_parser = subparsers.add_parser(
        "debate", help="3つのAIエージェントに討論させ、結論レポートを生成する"
    )
    debate_parser.add_argument("topic", help="討論させたいテーマ")
    debate_parser.add_argument(
        "--rounds", type=int, default=3, help="討論のラウンド数(既定: 3)"
    )
    debate_parser.add_argument(
        "--skip-feedback",
        action="store_true",
        help="討論後のフィードバック入力をスキップする(自動実行・テスト用)",
    )

    memory_parser = subparsers.add_parser("memory", help="記憶圧縮システムを手動操作する")
    memory_subparsers = memory_parser.add_subparsers(dest="memory_command", required=True)
    memory_subparsers.add_parser("sleep", help="睡眠モードを今すぐ実行し、海馬→新皮質へ記憶を圧縮する")
    memory_subparsers.add_parser("list", help="新皮質(長期記憶)に保存されている記憶を一覧表示する")

    corpus_parser = subparsers.add_parser("corpus", help="文学的感性コーパスを手動操作する")
    corpus_subparsers = corpus_parser.add_subparsers(dest="corpus_command", required=True)
    corpus_ingest_parser = corpus_subparsers.add_parser(
        "ingest", help="青空文庫の厳選作品を取り込み、文体・情緒表現のスタイル記述子を生成する"
    )
    corpus_ingest_parser.add_argument(
        "--force", action="store_true", help="キャッシュ・既存メモリを無視して再取得・再生成する"
    )
    corpus_subparsers.add_parser("list", help="取り込み済みのスタイル記述子を一覧表示する")
    corpus_subparsers.add_parser(
        "archive-crawl", help="青空文庫全体を少しずつ取り込む(本日分。手動・launchd両対応)"
    )
    corpus_subparsers.add_parser("archive-status", help="青空文庫全体クロールの進捗を表示する")

    study_parser = subparsers.add_parser("study", help="夜間修行(メンターAIとの自律学習)を手動操作する")
    study_subparsers = study_parser.add_subparsers(dest="study_command", required=True)
    study_subparsers.add_parser(
        "run", help="夜間修行を今すぐ実行する(GEMINI_API_KEYが必要。手動・launchd両対応)"
    )
    study_subparsers.add_parser("report", help="直近の夜間修行の結果を表示する")

    api_parser = subparsers.add_parser(
        "api", help="志粋の頭脳をHTTP API(FastAPI)として起動する(将来のNext.jsフロントエンド向け)"
    )
    api_parser.add_argument("--port", type=int, default=8000, help="待ち受けポート(既定: 8000)")

    subparsers.add_parser(
        "debate-autonomous",
        help="志粋が自分の弱点トピックについて自律的に討論する(夜間修行とは別ジョブ)",
    )

    evolution_parser = subparsers.add_parser(
        "evolution", help="自己修復プロトコル(エラー検知→修正案生成→人間承認)を操作する"
    )
    evolution_subparsers = evolution_parser.add_subparsers(dest="evolution_command", required=True)
    evolution_subparsers.add_parser("scan", help="未レビューのエラーから修正案を生成する")
    evolution_subparsers.add_parser("list", help="承認待ちの修正案を一覧する")
    evolution_show_parser = evolution_subparsers.add_parser("show", help="修正案の詳細(diff)を表示する")
    evolution_show_parser.add_argument("id", help="修正案のID")
    evolution_apply_parser = evolution_subparsers.add_parser(
        "apply", help="修正案を実ファイルに適用してコミットする(作業ツリーがクリーンな時のみ)"
    )
    evolution_apply_parser.add_argument("id", help="修正案のID")
    evolution_reject_parser = evolution_subparsers.add_parser("reject", help="修正案を却下する")
    evolution_reject_parser.add_argument("id", help="修正案のID")
    evolution_subparsers.add_parser(
        "feedback-list",
        help="例外は起きていないが会話中にユーザーから訂正・不満が伝えられた履歴を一覧する",
    )
    evolution_feedback_dismiss_parser = evolution_subparsers.add_parser(
        "feedback-dismiss", help="訂正・不満の履歴をレビュー済みにする"
    )
    evolution_feedback_dismiss_parser.add_argument("id", help="履歴のID")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "research":
            return run_research(args.topic, args.max_results)
        if args.command == "minutes":
            return run_minutes(args.audio_path)
        if args.command == "voicechat":
            return run_voicechat()
        if args.command == "debate":
            return run_debate(args.topic, args.rounds, args.skip_feedback)
        if args.command == "memory":
            if args.memory_command == "sleep":
                return run_memory_sleep()
            if args.memory_command == "list":
                return run_memory_list()
        if args.command == "corpus":
            if args.corpus_command == "ingest":
                return run_corpus_ingest(args.force)
            if args.corpus_command == "list":
                return run_corpus_list()
            if args.corpus_command == "archive-crawl":
                return run_corpus_archive_crawl()
            if args.corpus_command == "archive-status":
                return run_corpus_archive_status()
        if args.command == "study":
            if args.study_command == "run":
                return run_study_run()
            if args.study_command == "report":
                return run_study_report()
        if args.command == "api":
            return run_api(args.port)
        if args.command == "debate-autonomous":
            return run_debate_autonomous()
        if args.command == "evolution":
            if args.evolution_command == "scan":
                return run_evolution_scan()
            if args.evolution_command == "list":
                return run_evolution_list()
            if args.evolution_command == "show":
                return run_evolution_show(args.id)
            if args.evolution_command == "apply":
                return run_evolution_apply(args.id)
            if args.evolution_command == "reject":
                return run_evolution_reject(args.id)
            if args.evolution_command == "feedback-list":
                return run_evolution_feedback_list()
            if args.evolution_command == "feedback-dismiss":
                return run_evolution_feedback_dismiss(args.id)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[bold red]エラーが発生しました[/bold red]: {exc}")
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
