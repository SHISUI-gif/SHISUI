"""ユーザー登録・ログイン・セッション(src/core/auth.py)を検証する。"""
from src.core import auth


def test_register_creates_user_and_session(monkeypatch, tmp_path):
    monkeypatch.setattr(auth, "HIPPOCAMPUS_DB_PATH", tmp_path / "hippocampus.sqlite3")

    result = auth.register("那由多", "hunter2")

    assert result.success is True
    assert result.name == "那由多"
    assert result.token is not None
    assert auth.get_user_id_for_token(result.token) == result.user_id


def test_register_rejects_duplicate_name(monkeypatch, tmp_path):
    monkeypatch.setattr(auth, "HIPPOCAMPUS_DB_PATH", tmp_path / "hippocampus.sqlite3")

    auth.register("那由多", "hunter2")
    result = auth.register("那由多", "別のパスワード")

    assert result.success is False
    assert "既に使われています" in result.error


def test_login_succeeds_with_correct_password(monkeypatch, tmp_path):
    monkeypatch.setattr(auth, "HIPPOCAMPUS_DB_PATH", tmp_path / "hippocampus.sqlite3")

    registered = auth.register("那由多", "hunter2")
    result = auth.login("那由多", "hunter2")

    assert result.success is True
    assert result.user_id == registered.user_id
    # ログインごとに新しいトークンが発行される
    assert result.token != registered.token
    assert auth.get_user_id_for_token(result.token) == registered.user_id


def test_login_fails_with_wrong_password(monkeypatch, tmp_path):
    monkeypatch.setattr(auth, "HIPPOCAMPUS_DB_PATH", tmp_path / "hippocampus.sqlite3")

    auth.register("那由多", "hunter2")
    result = auth.login("那由多", "間違ったパスワード")

    assert result.success is False
    assert "パスワードが違います" in result.error


def test_login_fails_for_unknown_name(monkeypatch, tmp_path):
    monkeypatch.setattr(auth, "HIPPOCAMPUS_DB_PATH", tmp_path / "hippocampus.sqlite3")

    result = auth.login("存在しない名前", "何か")

    assert result.success is False


def test_get_user_id_for_token_returns_none_for_invalid_token(monkeypatch, tmp_path):
    monkeypatch.setattr(auth, "HIPPOCAMPUS_DB_PATH", tmp_path / "hippocampus.sqlite3")

    assert auth.get_user_id_for_token("存在しないトークン") is None


def test_login_locks_out_after_too_many_failed_attempts(monkeypatch, tmp_path):
    """総当たり対策: 同じ名前への失敗が閾値を超えたら、正しいパスワードでも弾く。"""
    monkeypatch.setattr(auth, "HIPPOCAMPUS_DB_PATH", tmp_path / "hippocampus.sqlite3")
    auth.register("那由多", "hunter2")

    for _ in range(auth._MAX_FAILED_ATTEMPTS):
        result = auth.login("那由多", "間違ったパスワード")
        assert result.success is False

    locked_out = auth.login("那由多", "hunter2")  # 正しいパスワードでもロック中は失敗する

    assert locked_out.success is False
    assert "試行が多すぎます" in locked_out.error


def test_login_lockout_is_scoped_per_name(monkeypatch, tmp_path):
    """あるユーザーへの総当たりが、別のユーザーのログインを巻き込んでロックしないこと。"""
    monkeypatch.setattr(auth, "HIPPOCAMPUS_DB_PATH", tmp_path / "hippocampus.sqlite3")
    auth.register("那由多", "hunter2")
    auth.register("別のユーザー", "別のパスワード")

    for _ in range(auth._MAX_FAILED_ATTEMPTS):
        auth.login("那由多", "間違ったパスワード")

    result = auth.login("別のユーザー", "別のパスワード")

    assert result.success is True


def test_successful_login_clears_failed_attempt_history(monkeypatch, tmp_path):
    """ロック閾値未満の失敗の後に成功すれば、カウントはリセットされる。"""
    monkeypatch.setattr(auth, "HIPPOCAMPUS_DB_PATH", tmp_path / "hippocampus.sqlite3")
    auth.register("那由多", "hunter2")

    for _ in range(auth._MAX_FAILED_ATTEMPTS - 1):
        auth.login("那由多", "間違ったパスワード")
    assert auth.login("那由多", "hunter2").success is True

    # リセットされているので、続けて数回失敗してもまだロックされない
    for _ in range(auth._MAX_FAILED_ATTEMPTS - 1):
        auth.login("那由多", "間違ったパスワード")
    assert auth.login("那由多", "hunter2").success is True
