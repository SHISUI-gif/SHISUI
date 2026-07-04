"""ユーザー登録・ログイン・セッション管理。

「本格的な認証」というより、友達それぞれの会話履歴・記憶を混ぜない/覗き見しない
ための最低限の区別。パスワードはhashlib.pbkdf2_hmac + ランダムsaltでハッシュ化する
(bcrypt等の新規依存を増やさないため、標準ライブラリのみで実装する)。

users・sessionsテーブルは、海馬(episodes)と同じHIPPOCAMPUS_DB_PATHに間借りする
(新しいSQLiteファイルを増やさない設計判断)。
"""
from __future__ import annotations

import hashlib
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from config.settings import HIPPOCAMPUS_DB_PATH

_PBKDF2_ITERATIONS = 260_000

# 総当たり(ブルートフォース)対策: 同じ名前への失敗ログインが一定回数を超えたら
# 一時的にロックする。トンネルURLを知っている・偶然踏んだ第三者が友達の
# パスワードを機械的に試し続けられないようにするための最低限の防御。
_MAX_FAILED_ATTEMPTS = 5
_LOCKOUT_WINDOW_MINUTES = 15


@dataclass
class AuthResult:
    success: bool
    user_id: int | None = None
    name: str | None = None
    token: str | None = None
    error: str | None = None


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(HIPPOCAMPUS_DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS login_attempts (
            name TEXT NOT NULL,
            attempted_at TEXT NOT NULL
        )
        """
    )
    return conn


def _recent_failed_attempts(conn: sqlite3.Connection, name: str) -> int:
    cutoff = (datetime.now() - timedelta(minutes=_LOCKOUT_WINDOW_MINUTES)).isoformat(
        timespec="seconds"
    )
    row = conn.execute(
        "SELECT COUNT(*) FROM login_attempts WHERE name = ? AND attempted_at >= ?", (name, cutoff)
    ).fetchone()
    return row[0]


def _record_failed_attempt(conn: sqlite3.Connection, name: str) -> None:
    conn.execute(
        "INSERT INTO login_attempts (name, attempted_at) VALUES (?, ?)",
        (name, datetime.now().isoformat(timespec="seconds")),
    )


def _clear_failed_attempts(conn: sqlite3.Connection, name: str) -> None:
    conn.execute("DELETE FROM login_attempts WHERE name = ?", (name,))


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), _PBKDF2_ITERATIONS
    ).hex()


def _issue_session(conn: sqlite3.Connection, user_id: int) -> str:
    token = uuid.uuid4().hex
    conn.execute(
        "INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)",
        (token, user_id, datetime.now().isoformat(timespec="seconds")),
    )
    return token


def register(name: str, password: str) -> AuthResult:
    """新規ユーザーを登録する。名前が既に使われていれば失敗する。"""
    name = name.strip()
    if not name or not password:
        return AuthResult(success=False, error="名前とパスワードを入力してください。")

    with _connect() as conn:
        existing = conn.execute("SELECT id FROM users WHERE name = ?", (name,)).fetchone()
        if existing:
            return AuthResult(success=False, error="その名前は既に使われています。")

        salt = uuid.uuid4().hex
        password_hash = _hash_password(password, salt)
        cursor = conn.execute(
            "INSERT INTO users (name, password_hash, salt, created_at) VALUES (?, ?, ?, ?)",
            (name, password_hash, salt, datetime.now().isoformat(timespec="seconds")),
        )
        user_id = cursor.lastrowid
        token = _issue_session(conn, user_id)

    return AuthResult(success=True, user_id=user_id, name=name, token=token)


def login(name: str, password: str) -> AuthResult:
    """既存ユーザーでログインする。名前が無い・パスワードが違えば失敗する。

    同じ名前への失敗が_LOCKOUT_WINDOW_MINUTES分以内に_MAX_FAILED_ATTEMPTS回を
    超えていたら、パスワードの正誤に関わらずロックする(総当たり対策)。
    """
    name = name.strip()

    with _connect() as conn:
        if _recent_failed_attempts(conn, name) >= _MAX_FAILED_ATTEMPTS:
            return AuthResult(
                success=False,
                error=(
                    f"ログイン試行が多すぎます。{_LOCKOUT_WINDOW_MINUTES}分待ってから"
                    "もう一度試してください。"
                ),
            )

        row = conn.execute(
            "SELECT id, password_hash, salt FROM users WHERE name = ?", (name,)
        ).fetchone()
        if row is None:
            _record_failed_attempt(conn, name)
            return AuthResult(success=False, error="その名前のユーザーは見つかりませんでした。")

        user_id, stored_hash, salt = row
        if _hash_password(password, salt) != stored_hash:
            _record_failed_attempt(conn, name)
            return AuthResult(success=False, error="パスワードが違います。")

        _clear_failed_attempts(conn, name)
        token = _issue_session(conn, user_id)

    return AuthResult(success=True, user_id=user_id, name=name, token=token)


def get_user_id_for_token(token: str) -> int | None:
    """セッショントークンからuser_idを引く。無効なトークンならNoneを返す。"""
    with _connect() as conn:
        row = conn.execute("SELECT user_id FROM sessions WHERE token = ?", (token,)).fetchone()
    return row[0] if row else None
