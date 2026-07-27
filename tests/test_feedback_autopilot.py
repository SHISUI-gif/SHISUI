"""要望・フィードバックの自動反映(src/core/feedback_autopilot.py)を検証する。

evolution.py側のgit/テスト実行はモックし、_select_file/_generate_fix_text
(LLM呼び出しに相当)だけを差し替えて、ファイル選定→diff生成→テストゲート
付き適用→user_feedback/activity_logへの反映までの配線を検証する。
"""
import dataclasses
import subprocess

import pytest

from src.core import activity_log, evolution, feedback_autopilot, user_feedback


@pytest.fixture
def isolated(monkeypatch, tmp_path):
    pending_dir = tmp_path / "pending"
    pending_dir.mkdir()
    monkeypatch.setattr(evolution, "BASE_DIR", tmp_path)
    monkeypatch.setattr(evolution, "PENDING_PATCHES_DIR", pending_dir)
    monkeypatch.setattr(feedback_autopilot, "BASE_DIR", tmp_path)
    monkeypatch.setattr(user_feedback, "USER_FEEDBACK_FILE", tmp_path / "user_feedback.json")
    monkeypatch.setattr(activity_log, "ACTIVITY_LOG_FILE", tmp_path / "activity_log.json")
    monkeypatch.setattr(
        evolution, "settings", dataclasses.replace(evolution.settings, evolution_auto_apply=True)
    )
    monkeypatch.setattr(
        feedback_autopilot,
        "settings",
        dataclasses.replace(feedback_autopilot.settings, evolution_auto_apply=True),
    )
    return tmp_path


def _make_persona_file(base_dir):
    path = base_dir / "src" / "common" / "persona.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('SHISUI_SYSTEM_PROMPT = "テスト用の元のプロンプト"\n', encoding="utf-8")
    return path


def _fake_git_run(applies_ok=True):
    def fake_run(cmd, **kwargs):
        if cmd[:2] == ["git", "status"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="")
        if cmd[:2] == ["git", "apply"]:
            return subprocess.CompletedProcess(cmd, 0 if applies_ok else 1, stdout="", stderr="")
        if cmd[:2] == ["git", "checkout"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="")
        if cmd[:2] == ["git", "clean"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="")
        if cmd[:2] == ["git", "commit"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="")
        raise AssertionError(f"想定外のコマンド: {cmd}")

    return fake_run


def test_process_feedback_applies_matched_file_when_tests_pass(isolated, monkeypatch):
    base_dir = isolated
    _make_persona_file(base_dir)
    record = user_feedback.submit_feedback(1, "那由多", "もっとフランクに話して")

    monkeypatch.setattr(feedback_autopilot, "_select_file", lambda content: "src/common/persona.py")
    monkeypatch.setattr(
        evolution,
        "_generate_fix_text",
        lambda prompt: "フランクな口調に寄せました。\n```diff\n--- a/src/common/persona.py\n"
        "+++ b/src/common/persona.py\n@@ -1 +1 @@\n"
        '-SHISUI_SYSTEM_PROMPT = "テスト用の元のプロンプト"\n'
        '+SHISUI_SYSTEM_PROMPT = "テスト用のフランクなプロンプト"\n```',
    )
    monkeypatch.setattr(subprocess, "run", _fake_git_run(applies_ok=True))
    monkeypatch.setattr(evolution, "_run_tests", lambda: (True, ""))

    result = feedback_autopilot.process_feedback(record["id"])

    assert result == "APPLIED"
    saved = {r["id"]: r for r in user_feedback.get_all_feedback()}[record["id"]]
    assert saved["reviewed"] is True
    assert saved["applied_proposal_id"]

    recent = activity_log.get_recent_activity()
    assert len(recent) == 1
    assert recent[0]["kind"] == "self_repair"
    assert recent[0]["details"]["applied"] is True


def test_process_feedback_leaves_for_human_review_when_no_file_matches(isolated, monkeypatch):
    record = user_feedback.submit_feedback(1, "那由多", "曖昧すぎる謎の要望")

    monkeypatch.setattr(feedback_autopilot, "_select_file", lambda content: None)

    def fail_generate(prompt):
        raise AssertionError("ファイルが選定できない場合はdiff生成を呼ぶべきではない")

    monkeypatch.setattr(evolution, "_generate_fix_text", fail_generate)

    result = feedback_autopilot.process_feedback(record["id"])

    assert result == "NO_MATCH"
    saved = {r["id"]: r for r in user_feedback.get_all_feedback()}[record["id"]]
    assert saved["reviewed"] is False
    assert "applied_proposal_id" not in saved


def test_process_feedback_leaves_for_human_review_when_tests_fail(isolated, monkeypatch):
    base_dir = isolated
    _make_persona_file(base_dir)
    record = user_feedback.submit_feedback(1, "那由多", "もっとフランクに話して")

    monkeypatch.setattr(feedback_autopilot, "_select_file", lambda content: "src/common/persona.py")
    monkeypatch.setattr(
        evolution,
        "_generate_fix_text",
        lambda prompt: "```diff\n--- a/src/common/persona.py\n+++ b/src/common/persona.py\n"
        "@@ -1 +1 @@\n-old\n+new\n```",
    )
    monkeypatch.setattr(subprocess, "run", _fake_git_run(applies_ok=True))
    monkeypatch.setattr(evolution, "_run_tests", lambda: (False, "1 failed"))

    result = feedback_autopilot.process_feedback(record["id"])

    assert result == "TEST_FAILED"
    saved = {r["id"]: r for r in user_feedback.get_all_feedback()}[record["id"]]
    assert saved["reviewed"] is False


def test_select_file_returns_none_on_empty_llm_response(monkeypatch):
    """2026-07-28に本番で実際に発生: LLMが空文字列(改行すら無い)を返すと
    text.strip().splitlines()[0]がIndexErrorでクラッシュしていた。"NONE"と
    同じ「該当なし」として扱うべき。"""
    monkeypatch.setattr(evolution, "_generate_fix_text", lambda prompt: "")

    assert feedback_autopilot._select_file("何かの要望") is None


def test_process_feedback_skips_already_reviewed(isolated, monkeypatch):
    record = user_feedback.submit_feedback(1, "那由多", "何か要望")
    user_feedback.mark_reviewed(record["id"])

    def fail_select(content):
        raise AssertionError("既読済みのフィードバックは処理すべきではない")

    monkeypatch.setattr(feedback_autopilot, "_select_file", fail_select)

    assert feedback_autopilot.process_feedback(record["id"]) == "SKIPPED"


def test_process_feedback_disabled_by_setting(isolated, monkeypatch):
    record = user_feedback.submit_feedback(1, "那由多", "何か要望")
    monkeypatch.setattr(
        feedback_autopilot,
        "settings",
        dataclasses.replace(feedback_autopilot.settings, evolution_auto_apply=False),
    )

    def fail_select(content):
        raise AssertionError("無効化時はファイル選定すら呼ぶべきではない")

    monkeypatch.setattr(feedback_autopilot, "_select_file", fail_select)

    assert feedback_autopilot.process_feedback(record["id"]) == "AUTO_APPLY_DISABLED"
