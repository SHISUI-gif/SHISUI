"""FastAPI(src/api/main.py)の認証・会話エンドポイントを検証する。

実際のOllamaサーバーには接続せず、ollama.chat/ollama.embeddingsをモック化して
認証・会話のアクセス制御ロジックのみを検証する。
"""
import hashlib
import threading
import time
from dataclasses import dataclass

import ollama
import pytest
from fastapi.testclient import TestClient

from src.api import main
from src.core import activity_log, auth, evolution, user_feedback
from src.corpus import ingest as literary_ingest
from src.memory import avatar, conversations, hippocampus, neocortex


def _fake_embeddings(model: str, prompt: str) -> dict:
    digest = hashlib.sha256(prompt.encode("utf-8")).digest()
    return {"embedding": [b / 255.0 for b in digest[:16]]}


@dataclass
class _FakeSettings:
    owner_user_name: str = "那由多"


@pytest.fixture(autouse=True)
def _isolate_storage(tmp_path, monkeypatch):
    db_path = tmp_path / "hippocampus.sqlite3"
    monkeypatch.setattr(auth, "HIPPOCAMPUS_DB_PATH", db_path)
    monkeypatch.setattr(auth, "settings", _FakeSettings(owner_user_name="那由多"))
    monkeypatch.setattr(hippocampus, "HIPPOCAMPUS_DB_PATH", db_path)
    monkeypatch.setattr(conversations, "HIPPOCAMPUS_DB_PATH", db_path)
    monkeypatch.setattr(avatar, "HIPPOCAMPUS_DB_PATH", db_path)
    monkeypatch.setattr(neocortex, "NEOCORTEX_DB_DIR", tmp_path / "neocortex_chroma")
    monkeypatch.setattr(literary_ingest, "LITERARY_CHROMA_DIR", tmp_path / "literary_chroma")
    monkeypatch.setattr(activity_log, "ACTIVITY_LOG_FILE", tmp_path / "activity_log.json")
    monkeypatch.setattr(evolution, "PENDING_PATCHES_DIR", tmp_path / "pending")
    (tmp_path / "pending").mkdir()
    monkeypatch.setattr(user_feedback, "USER_FEEDBACK_FILE", tmp_path / "user_feedback.json")
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


def test_proactive_checkin_without_auth_returns_401(client):
    response = client.post("/api/conversations/1/proactive-checkin")
    assert response.status_code == 401


def test_proactive_checkin_returns_content_and_persists_to_history(client, monkeypatch):
    monkeypatch.setattr(ollama, "chat", _fake_chat)
    register = client.post("/api/auth/register", json={"name": "那由多", "password": "hunter2"})
    token = register.json()["token"]

    client.post(
        "/api/chat",
        json={"message": "カフェの話", "history": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    conversation_id = client.get(
        "/api/conversations", headers={"Authorization": f"Bearer {token}"}
    ).json()[0]["id"]

    def fake_checkin_chat(model, messages, stream=False):
        return {"message": {"content": "そういえばさっきの話、続き聞きたいな"}}

    monkeypatch.setattr(ollama, "chat", fake_checkin_chat)

    response = client.post(
        f"/api/conversations/{conversation_id}/proactive-checkin",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["content"] == "そういえばさっきの話、続き聞きたいな"

    history = client.get(
        f"/api/conversations/{conversation_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    assert history[-1] == {"role": "assistant", "content": "そういえばさっきの話、続き聞きたいな"}


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


def test_concurrent_chat_requests_queue_instead_of_hanging_silently(client, monkeypatch):
    """Ollamaは実質1リクエストずつしか処理できない(-np 1)。友達数人が同時に
    メッセージを送ったとき、後続のリクエストが無言のまま待たされると
    トンネルの無応答タイムアウトで502/524になる(実際に起きた不具合)。
    2人目には「順番待ち中」のステータスが届き続け、無言のまま待たされない
    ことを検証する。"""
    monkeypatch.setattr(main, "_QUEUE_POLL_SECONDS", 0.05)

    release_first = threading.Event()
    first_started = threading.Event()

    def slow_fake_chat(model, messages, tools=None, stream=False, think=None, keep_alive=None):
        if tools:
            return {"message": {"role": "assistant", "content": "", "tool_calls": None}}

        def gen():
            first_started.set()
            release_first.wait(timeout=5)
            yield {"message": {"content": "最初の返信"}}

        return gen()

    monkeypatch.setattr(ollama, "chat", slow_fake_chat)

    user1 = client.post("/api/auth/register", json={"name": "ユーザー1", "password": "pw1"}).json()
    user2 = client.post("/api/auth/register", json={"name": "ユーザー2", "password": "pw2"}).json()

    results = {}

    def run(name, token, message):
        response = client.post(
            "/api/chat",
            json={"message": message, "history": []},
            headers={"Authorization": f"Bearer {token}"},
        )
        results[name] = response.text

    thread1 = threading.Thread(target=run, args=("first", user1["token"], "1つ目"))
    thread1.start()
    assert first_started.wait(timeout=5)  # 1人目がロックを握ってOllama呼び出し中になるのを待つ

    thread2 = threading.Thread(target=run, args=("second", user2["token"], "2つ目"))
    thread2.start()
    time.sleep(0.3)  # 2人目が「順番待ち中」を数回ポーリングする時間を与える
    release_first.set()

    thread1.join(timeout=5)
    thread2.join(timeout=5)

    assert "最初の返信" in results["first"]
    assert "順番待ち中" in results["second"]


def test_avatar_requires_auth(client):
    response = client.get("/api/avatar")
    assert response.status_code == 401


def test_avatar_returns_empty_for_new_user(client):
    register = client.post("/api/auth/register", json={"name": "那由多", "password": "hunter2"})
    token = register.json()["token"]

    response = client.get("/api/avatar", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {"unlocked_items": [], "mood": None}


def test_avatar_returns_unlocked_items_with_catalog_metadata(client):
    register = client.post("/api/auth/register", json={"name": "那由多", "password": "hunter2"})
    body = register.json()
    avatar.unlock_item(body["user_id"], "bookish_glasses")

    response = client.get("/api/avatar", headers={"Authorization": f"Bearer {body['token']}"})

    unlocked = response.json()["unlocked_items"]
    assert len(unlocked) == 1
    assert unlocked[0]["slug"] == "bookish_glasses"
    assert unlocked[0]["display_name"] == "読書メガネ"
    assert unlocked[0]["asset"] == "bookish_glasses.png"


def test_avatar_items_are_scoped_per_user(client):
    user1 = client.post("/api/auth/register", json={"name": "ユーザー1", "password": "pw1"}).json()
    user2 = client.post("/api/auth/register", json={"name": "ユーザー2", "password": "pw2"}).json()
    avatar.unlock_item(user1["user_id"], "chef_hat")

    user1_avatar = client.get(
        "/api/avatar", headers={"Authorization": f"Bearer {user1['token']}"}
    ).json()
    user2_avatar = client.get(
        "/api/avatar", headers={"Authorization": f"Bearer {user2['token']}"}
    ).json()

    assert len(user1_avatar["unlocked_items"]) == 1
    assert user2_avatar["unlocked_items"] == []


def test_avatar_response_includes_mood_field(client):
    register = client.post("/api/auth/register", json={"name": "那由多", "password": "hunter2"})
    body = register.json()
    hippocampus.log_episode(
        role="user", content="やったー!", source="chat", user_id=body["user_id"], emotion="HAPPY"
    )

    response = client.get("/api/avatar", headers={"Authorization": f"Bearer {body['token']}"})

    assert response.json()["mood"] == "HAPPY"


def test_avatar_mood_is_scoped_per_user(client):
    user1 = client.post("/api/auth/register", json={"name": "ユーザー1", "password": "pw1"}).json()
    user2 = client.post("/api/auth/register", json={"name": "ユーザー2", "password": "pw2"}).json()
    hippocampus.log_episode(
        role="user", content="不安だな", source="chat", user_id=user1["user_id"], emotion="ANXIOUS"
    )

    user1_avatar = client.get(
        "/api/avatar", headers={"Authorization": f"Bearer {user1['token']}"}
    ).json()
    user2_avatar = client.get(
        "/api/avatar", headers={"Authorization": f"Bearer {user2['token']}"}
    ).json()

    assert user1_avatar["mood"] == "ANXIOUS"
    assert user2_avatar["mood"] is None


def test_activity_requires_auth(client):
    response = client.get("/api/activity")
    assert response.status_code == 401


def test_activity_returns_recent_log_entries(client):
    register = client.post("/api/auth/register", json={"name": "那由多", "password": "hunter2"})
    token = register.json()["token"]
    activity_log.log_activity(kind="sleep", summary="睡眠モードのテスト実行")

    response = client.get("/api/activity", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    activities = response.json()["activities"]
    assert len(activities) == 1
    assert activities[0]["kind"] == "sleep"
    assert activities[0]["summary"] == "睡眠モードのテスト実行"


def test_activity_is_shared_across_users_not_scoped(client):
    """活動ログは特定の友達のものではなく志粋自身の活動なので、誰がログインしても同じ内容が見える。"""
    user1 = client.post("/api/auth/register", json={"name": "ユーザー1", "password": "pw1"}).json()
    user2 = client.post("/api/auth/register", json={"name": "ユーザー2", "password": "pw2"}).json()
    activity_log.log_activity(kind="study", summary="夜間修行のテスト実行")

    user1_view = client.get(
        "/api/activity", headers={"Authorization": f"Bearer {user1['token']}"}
    ).json()
    user2_view = client.get(
        "/api/activity", headers={"Authorization": f"Bearer {user2['token']}"}
    ).json()

    assert user1_view == user2_view


def test_get_me_requires_auth(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_get_me_reports_owner_true_for_owner(client):
    register = client.post("/api/auth/register", json={"name": "那由多", "password": "hunter2"})
    body = register.json()

    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['token']}"})

    assert response.status_code == 200
    result = response.json()
    assert result["name"] == "那由多"
    assert result["is_owner"] is True


def test_get_me_reports_owner_false_for_non_owner(client):
    register = client.post("/api/auth/register", json={"name": "友達", "password": "pw"})
    body = register.json()

    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['token']}"})

    assert response.json()["is_owner"] is False


def test_feedback_submit_requires_auth(client):
    response = client.post("/api/feedback", json={"content": "要望です"})
    assert response.status_code == 401


def test_feedback_submit_records_submitter_from_token_not_body(client):
    register = client.post("/api/auth/register", json={"name": "友達", "password": "pw"})
    token = register.json()["token"]

    response = client.post(
        "/api/feedback",
        json={"content": "PDFも読めたら嬉しい"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    stored = user_feedback.get_all_feedback()
    assert len(stored) == 1
    assert stored[0]["user_name"] == "友達"
    assert stored[0]["content"] == "PDFも読めたら嬉しい"


def test_feedback_submit_rejects_empty_content(client):
    register = client.post("/api/auth/register", json={"name": "友達", "password": "pw"})
    token = register.json()["token"]

    response = client.post(
        "/api/feedback", json={"content": ""}, headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 422


def test_feedback_list_rejects_non_owner(client):
    register = client.post("/api/auth/register", json={"name": "友達", "password": "pw"})
    token = register.json()["token"]

    response = client.get("/api/feedback", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


def test_feedback_list_allows_owner(client):
    register = client.post("/api/auth/register", json={"name": "那由多", "password": "hunter2"})
    token = register.json()["token"]
    user_feedback.submit_feedback(register.json()["user_id"], "那由多", "テスト要望")

    response = client.get("/api/feedback", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_feedback_dismiss_rejects_non_owner(client):
    register = client.post("/api/auth/register", json={"name": "友達", "password": "pw"})
    token = register.json()["token"]
    record = user_feedback.submit_feedback(1, "友達", "テスト要望")

    response = client.post(
        f"/api/feedback/{record['id']}/dismiss", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403


def test_feedback_dismiss_allows_owner(client):
    register = client.post("/api/auth/register", json={"name": "那由多", "password": "hunter2"})
    token = register.json()["token"]
    record = user_feedback.submit_feedback(1, "友達", "テスト要望")

    response = client.post(
        f"/api/feedback/{record['id']}/dismiss", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert user_feedback.get_all_feedback()[0]["reviewed"] is True


def test_evolution_proposals_list_rejects_non_owner(client):
    register = client.post("/api/auth/register", json={"name": "友達", "password": "pw"})
    token = register.json()["token"]

    response = client.get("/api/evolution/proposals", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


def test_evolution_proposals_list_allows_owner(client):
    register = client.post("/api/auth/register", json={"name": "那由多", "password": "hunter2"})
    token = register.json()["token"]
    proposal = evolution.FixProposal(
        id="abc123", error_id="err1", file_path="src/buggy.py", explanation="説明", diff="diff"
    )
    evolution._save_proposal(proposal)

    response = client.get("/api/evolution/proposals", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == "abc123"


def test_evolution_proposal_get_404_for_unknown_id(client):
    register = client.post("/api/auth/register", json={"name": "那由多", "password": "hunter2"})
    token = register.json()["token"]

    response = client.get(
        "/api/evolution/proposals/doesnotexist", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 404


def test_evolution_proposal_apply_rejects_non_owner(client):
    register = client.post("/api/auth/register", json={"name": "友達", "password": "pw"})
    token = register.json()["token"]

    response = client.post(
        "/api/evolution/proposals/abc123/apply", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403


def test_evolution_proposal_apply_allows_owner_and_reports_result(client, monkeypatch):
    register = client.post("/api/auth/register", json={"name": "那由多", "password": "hunter2"})
    token = register.json()["token"]
    monkeypatch.setattr(evolution, "apply_proposal", lambda pid: (True, f"適用しました: {pid}"))

    response = client.post(
        "/api/evolution/proposals/abc123/apply", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "message": "適用しました: abc123"}


def test_evolution_proposal_reject_rejects_non_owner(client):
    register = client.post("/api/auth/register", json={"name": "友達", "password": "pw"})
    token = register.json()["token"]

    response = client.post(
        "/api/evolution/proposals/abc123/reject", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403
