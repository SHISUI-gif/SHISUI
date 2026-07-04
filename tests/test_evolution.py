"""自己修復プロトコル(src/core/evolution.py)を、Ollama・gitともにモックして検証する。"""
import subprocess

import ollama
import pytest

from src.core import error_log, evolution


@pytest.fixture
def isolated_evolution(monkeypatch, tmp_path):
    """BASE_DIR・エラーログ・pending保存先を、すべてtmp_path配下に隔離する。"""
    pending_dir = tmp_path / "pending"
    pending_dir.mkdir()
    monkeypatch.setattr(evolution, "BASE_DIR", tmp_path)
    monkeypatch.setattr(evolution, "PENDING_PATCHES_DIR", pending_dir)
    monkeypatch.setattr(error_log, "ERROR_LOG_FILE", tmp_path / "error_log.json")
    return tmp_path, pending_dir


def _make_buggy_file(base_dir, relative="src/buggy.py"):
    path = base_dir / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("def broken():\n    return 1 / 0\n", encoding="utf-8")
    return path


def _traceback_for(path) -> str:
    return f'Traceback (most recent call last):\n  File "{path}", line 2, in broken\nZeroDivisionError: division by zero\n'


def test_generate_fix_proposals_creates_pending_patch(isolated_evolution, monkeypatch):
    base_dir, pending_dir = isolated_evolution
    buggy_file = _make_buggy_file(base_dir)
    error_log.log_error("some_source", ZeroDivisionError("division by zero"))
    # log_errorはtraceback.format_exc()を使うため、実際に発生したエラーとして記録し直す
    records = error_log._load_all()
    records[0]["traceback"] = _traceback_for(buggy_file)
    error_log._save_all(records)

    fake_diff = (
        "--- a/src/buggy.py\n+++ b/src/buggy.py\n@@ -1,2 +1,2 @@\n"
        " def broken():\n-    return 1 / 0\n+    return 0\n"
    )

    def fake_chat(model, messages):
        return {"message": {"content": f"ゼロ除算を直しました。\n```diff\n{fake_diff}```"}}

    monkeypatch.setattr(ollama, "chat", fake_chat)

    proposals = evolution.generate_fix_proposals()

    assert len(proposals) == 1
    assert proposals[0].file_path == "src/buggy.py"
    assert "1 / 0" in proposals[0].diff or "return 0" in proposals[0].diff
    assert error_log.get_unreviewed_errors() == []
    assert len(list(pending_dir.glob("*.json"))) == 1


def test_generate_fix_proposals_skips_when_file_not_in_project(isolated_evolution, monkeypatch):
    error_log.log_error("some_source", ValueError("何か"))
    records = error_log._load_all()
    records[0]["traceback"] = 'File "/some/outside/path.py", line 1\nValueError: 何か\n'
    error_log._save_all(records)

    def fake_chat(model, messages):
        raise AssertionError("ファイルが特定できない場合はLLMを呼ぶべきではない")

    monkeypatch.setattr(ollama, "chat", fake_chat)

    proposals = evolution.generate_fix_proposals()

    assert proposals == []
    assert error_log.get_unreviewed_errors() == []


def test_generate_fix_proposals_skips_when_llm_returns_no_diff(isolated_evolution, monkeypatch):
    base_dir, pending_dir = isolated_evolution
    buggy_file = _make_buggy_file(base_dir)
    error_log.log_error("some_source", ZeroDivisionError("division by zero"))
    records = error_log._load_all()
    records[0]["traceback"] = _traceback_for(buggy_file)
    error_log._save_all(records)

    monkeypatch.setattr(
        ollama, "chat", lambda model, messages: {"message": {"content": "よく分かりませんでした。"}}
    )

    proposals = evolution.generate_fix_proposals()

    assert proposals == []
    assert list(pending_dir.glob("*.json")) == []
    assert error_log.get_unreviewed_errors() == []


def test_apply_proposal_refuses_when_working_tree_dirty(isolated_evolution, monkeypatch):
    _, pending_dir = isolated_evolution
    proposal = evolution.FixProposal(
        id="abc123", error_id="err1", file_path="src/buggy.py", explanation="説明", diff="diff"
    )
    evolution._save_proposal(proposal)

    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout=" M src/buggy.py\n")
    )

    ok, message = evolution.apply_proposal("abc123")

    assert ok is False
    assert "未コミット" in message
    assert (pending_dir / "abc123.json").exists()


def test_apply_proposal_succeeds_and_commits_when_clean(isolated_evolution, monkeypatch):
    _, pending_dir = isolated_evolution
    proposal = evolution.FixProposal(
        id="abc123", error_id="err1", file_path="src/buggy.py", explanation="説明", diff="diff-content"
    )
    evolution._save_proposal(proposal)

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[:2] == ["git", "status"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="")
        if cmd[:2] == ["git", "apply"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if cmd[:2] == ["git", "commit"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="")
        raise AssertionError(f"想定外のコマンド: {cmd}")

    monkeypatch.setattr(subprocess, "run", fake_run)

    ok, message = evolution.apply_proposal("abc123")

    assert ok is True
    assert "src/buggy.py" in message
    assert not (pending_dir / "abc123.json").exists()
    assert any(cmd[:2] == ["git", "commit"] for cmd in calls)


def test_reject_proposal_removes_pending_file(isolated_evolution):
    _, pending_dir = isolated_evolution
    proposal = evolution.FixProposal(
        id="abc123", error_id="err1", file_path="src/buggy.py", explanation="説明", diff="diff"
    )
    evolution._save_proposal(proposal)

    assert evolution.reject_proposal("abc123") is True
    assert not (pending_dir / "abc123.json").exists()
    assert evolution.reject_proposal("abc123") is False
