"""例外を伴わない「ユーザーからの訂正・不満」ログ(src/core/feedback_log.py)を検証する。"""
from src.core import feedback_log


def test_looks_like_correction_detects_common_phrases():
    assert feedback_log.looks_like_correction("それ違うよ")
    assert feedback_log.looks_like_correction("全然機能してないじゃん")
    assert feedback_log.looks_like_correction("まだ直ってないよ")
    assert not feedback_log.looks_like_correction("ありがとう、助かった!")
    assert not feedback_log.looks_like_correction("次は何しようか")


def test_looks_like_correction_detects_presumptuous_phrasing():
    """「決めつけ」系は元のキーワード一覧に無く、実際に検知漏れしていた訂正の再発防止テスト。"""
    assert feedback_log.looks_like_correction("そこまで好きではないな、決めつけるの気をつけて")
    assert feedback_log.looks_like_correction("勝手に思い込まないでほしい")
    assert feedback_log.looks_like_correction("そんなこと言ってないよ")


def test_log_feedback_appends_and_marks_unreviewed(monkeypatch, tmp_path):
    monkeypatch.setattr(feedback_log, "FEEDBACK_LOG_FILE", tmp_path / "feedback_log.json")

    record = feedback_log.log_feedback(
        previous_user_message="来期のアニメ教えて",
        previous_assistant_response="2023年冬のアニメは...",
        correction_message="それ違うよ、今は2026年だよ",
    )

    assert record["previous_user_message"] == "来期のアニメ教えて"
    assert record["correction_message"] == "それ違うよ、今は2026年だよ"
    assert record["reviewed"] is False

    unreviewed = feedback_log.get_unreviewed_feedback()
    assert len(unreviewed) == 1
    assert unreviewed[0]["id"] == record["id"]


def test_mark_reviewed_excludes_from_unreviewed(monkeypatch, tmp_path):
    monkeypatch.setattr(feedback_log, "FEEDBACK_LOG_FILE", tmp_path / "feedback_log.json")

    record = feedback_log.log_feedback("質問", "回答", "違うよ")
    feedback_log.mark_reviewed(record["id"])

    assert feedback_log.get_unreviewed_feedback() == []
