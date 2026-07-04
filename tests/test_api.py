"""FastAPI(src/api/main.py)の認証・会話エンドポイントを検証する。

実際のOllamaサーバーには接続せず、ollama.chat/ollama.embeddingsをモック化して
認証・会話のアクセス制御ロジックのみを検証する。
"""
import hashlib

import ollama
import pytest
from fastapi.testclient import TestClient

from src.api import main
from src.core import auth
from src.corpus import ingest as literary_ingest
from src.memory import conversations, hippocampus, neocortex


def _fake_embeddings(model: str, prompt: str) -> dict:
    digest = hashlib.sha256(prompt.encode("utf-8")).digest()
    return {"embedding": [b / 255.0 for b in digest[:16]]}


@pytest.fixture(autouse=True)
def _isolate_storage(tmp_path, monkeypatch):
    db_path = tmp_path / "hippocampus.sqlite3"
    monkeypatch.setattr(auth, "HIPPOCAMPUS_DB_PATH", db_path)
    monkeypatch.setattr(hippocampus, "HIPPOCAMPUS_DB_PATH", db_path)
    monkeypatch.setattr(conversations, "HIPPOCAMPUS_DB_PATH", db_path)
    monkeypatch.setattr(neocortex, "NEOCORTEX_DB_DIR", tmp_path / "neocortex_chroma")
    monkeypatch.setattr(literary_ingest, "LITERARY_CHROMA_DIR", tmp_path / "literary_chroma")
    monkeypatch.setattr(ollama, "embeddings", _fake_embeddings)


@pytest.fixture
def client():
    return TestClient(main.app)


def _fake_chat(model, messages, tools=None, stream=False, think=None, keep_alive=None):
    if tools:
        return {"message": {"role": "assistant", "content": "", "tool_calls": None}}

    def gen():
        yield {"message": {"content": "了解!"}}

    return gen()


def test_register_returns_token(client):
    response = client.post("/api/auth/register", json={"name": "那由多", "password": "hunter2"})

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "那由多"
    assert body["token"]


def test_register_rejects_duplicate_name(client):
    client.post("/api/auth/register", json={"name": "那由多", "password": "hunter2"})
    response = client.post("/api/auth/register", json={"name": "那由多", "password": "別の"})

    assert response.status_code == 409


def test_login_with_correct_password_succeeds(client):
    client.post("/api/auth/register", json={"name": "那由多", "password": "hunter2"})
    response = client.post("/api/auth/login", json={"name": "那由多", "password": "hunter2"})

    assert response.status_code == 200
    assert response.json()["token"]


def test_login_with_wrong_password_fails(client):
    client.post("/api/auth/register", json={"name": "那由多", "password": "hunter2"})
    response = client.post("/api/auth/login", json={"name": "那由多", "password": "間違い"})

    assert response.status_code == 401


def test_chat_without_auth_header_returns_401(client):
    response = client.post("/api/chat", json={"message": "こんにちは", "history": []})
    assert response.status_code == 401


def test_chat_with_invalid_token_returns_401(client):
    # HTTPヘッダーはASCIIのみなので、実際のトークン(uuid4().hex)と同じ形式で試す
    response = client.post(
        "/api/chat",
        json={"message": "こんにちは", "history": []},
        headers={"Authorization": "Bearer 0000000000000000000000000000dead"},
    )
    assert response.status_code == 401


def test_chat_with_valid_token_streams_response(client, monkeypatch):
    monkeypatch.setattr(ollama, "chat", _fake_chat)
    register = client.post("/api/auth/register", json={"name": "那由多", "password": "hunter2"})
    token = register.json()["token"]

    response = client.post(
        "/api/chat",
        json={"message": "こんにちは", "history": []},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert "了解" in response.text


def test_conversations_list_requires_auth(client):
    response = client.get("/api/conversations")
    assert response.status_code == 401


def test_conversations_only_show_own_threads(client, monkeypatch):
    monkeypatch.setattr(ollama, "chat", _fake_chat)

    user1 = client.post("/api/auth/register", json={"name": "ユーザー1", "password": "pw1"}).json()
    user2 = client.post("/api/auth/register", json={"name": "ユーザー2", "password": "pw2"}).json()

    client.post(
        "/api/chat",
        json={"message": "ユーザー1の会話", "history": []},
        headers={"Authorization": f"Bearer {user1['token']}"},
    )

    user1_threads = client.get(
        "/api/conversations", headers={"Authorization": f"Bearer {user1['token']}"}
    ).json()
    user2_threads = client.get(
        "/api/conversations", headers={"Authorization": f"Bearer {user2['token']}"}
    ).json()

    assert len(user1_threads) == 1
    assert len(user2_threads) == 0


def test_conversation_messages_hidden_from_non_owner(client, monkeypatch):
    monkeypatch.setattr(ollama, "chat", _fake_chat)

    user1 = client.post("/api/auth/register", json={"name": "ユーザー1", "password": "pw1"}).json()
    user2 = client.post("/api/auth/register", json={"name": "ユーザー2", "password": "pw2"}).json()

    client.post(
        "/api/chat",
        json={"message": "秘密の相談", "history": []},
        headers={"Authorization": f"Bearer {user1['token']}"},
    )
    conversation_id = client.get(
        "/api/conversations", headers={"Authorization": f"Bearer {user1['token']}"}
    ).json()[0]["id"]

    own_view = client.get(
        f"/api/conversations/{conversation_id}/messages",
        headers={"Authorization": f"Bearer {user1['token']}"},
    ).json()
    other_view = client.get(
        f"/api/conversations/{conversation_id}/messages",
        headers={"Authorization": f"Bearer {user2['token']}"},
    ).json()

    assert len(own_view) > 0
    assert other_view == []
