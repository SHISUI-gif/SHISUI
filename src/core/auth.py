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
from datetime import datetime

from config.settings import HIPPOCAMPUS_DB_PATH

_PBKDF2_ITERATIONS = 260_000


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
    return conn


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
    """既存ユーザーでログインする。名前が無い・パスワードが違えば失敗する。"""
    name = name.strip()

    with _connect() as conn:
        row = conn.execute(
            "SELECT id, password_hash, salt FROM users WHERE name = ?", (name,)
        ).fetchone()
        if row is None:
            return AuthResult(success=False, error="その名前のユーザーは見つかりませんでした。")

        user_id, stored_hash, salt = row
        if _hash_password(password, salt) != stored_hash:
            return AuthResult(success=False, error="パスワードが違います。")

        token = _issue_session(conn, user_id)

    return AuthResult(success=True, user_id=user_id, name=name, token=token)


def get_user_id_for_token(token: str) -> int | None:
    """セッショントークンからuser_idを引く。無効なトークンならNoneを返す。"""
    with _connect() as conn:
        row = conn.execute("SELECT user_id FROM sessions WHERE token = ?", (token,)).fetchone()
    return row[0] if row else None
