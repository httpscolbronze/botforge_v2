"""End-to-end persistence, model discovery and permission tests.

Run from the project root:

    .venv/bin/python tests/test_persistence.py

The script starts a real uvicorn server against ``/tmp/bf-persist``, restarts
it, and verifies every requested persistence behaviour. Ollama is replaced by
``tests/stub_ollama.py`` because CI has no Ollama installation: discovery and
chat plumbing are real, model answer quality is not.
"""

import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
DATA = Path("/tmp/bf-persist")
STUB_MODELS = Path("/tmp/bf-stub-models.json")
BASE = "http://127.0.0.1:8001"
PY = str(ROOT / ".venv/bin/python")
PORT = "8001"

results = []


def check(name, condition, detail=""):
    results.append((name, bool(condition), detail))
    print(("PASS" if condition else "FAIL"), "-", name, ("| " + str(detail)[:300] if detail else ""))


def write_models(names):
    STUB_MODELS.write_text(json.dumps(names))


def start_stub():
    log = open("/tmp/bf-stub.log", "ab")
    return subprocess.Popen(
        [PY, str(ROOT / "tests/stub_ollama.py")],
        stdout=log,
        stderr=log,
        start_new_session=True,
    )


def start_app(tag):
    env = os.environ.copy()
    env.update(
        {
            "BOTFORGE_DATA_DIR": str(DATA),
            "OLLAMA_BASE_URL": "http://127.0.0.1:11455",
            "BOTFORGE_ADMIN_PASSWORD": "test-admin",
            "BOTFORGE_SESSION_SECRET": "test-secret",
            "BOTFORGE_EMBEDDING_FALLBACK": "true",
        }
    )
    log = open(f"/tmp/bf-app-{tag}.log", "ab")
    return subprocess.Popen(
        [PY, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", PORT],
        cwd=str(ROOT),
        env=env,
        stdout=log,
        stderr=log,
        start_new_session=True,
    )


def wait_ready(client, timeout=45):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if client.get(f"{BASE}/health", timeout=2).status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.4)
    return False


def stop(proc):
    if not proc:
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except Exception:
        pass
    try:
        proc.wait(timeout=15)
    except Exception:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except Exception:
            pass


def make_pdf(path):
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (72, 100),
        "Florence Nightingale founded modern nursing.\n"
        "She was born in 1820 and worked at Scutari during the Crimean War.\n"
        "Her statistical work saved many lives in military hospitals.",
    )
    doc.save(path)
    doc.close()


def main():
    shutil.rmtree(DATA, ignore_errors=True)
    DATA.mkdir(parents=True)
    write_models(["llama3.2:3b", "nomic-embed-text", "llava", "mistral:7b"])

    stub = start_stub()
    app = start_app("a")
    headers = {"X-Client-Id": "wsA"}
    headers_b = {"X-Client-Id": "wsB"}
    client = httpx.Client(timeout=60)
    try:
        check("server starts and /health responds", wait_ready(client))
        health = client.get(f"{BASE}/health").json()
        check("SQLite database initialised and reported", health["database"]["engine"] == "sqlite", health["database"])
        check("schema migrations recorded", bool(health["database"]["migrations"]), health["database"]["migrations"])

        login = client.post(f"{BASE}/auth/login", json={"password": "test-admin"})
        check("admin login", login.status_code == 200, login.text[:200])
        admin = {"Authorization": f"Bearer {login.json()['token']}"}

        status = client.get(f"{BASE}/models/status").json()
        check("Ollama discovery sees installed models", status["connected"] and status["counts"]["total"] == 4, status["counts"])
        check(
            "models are classified for chat and embeddings",
            status["counts"]["chat"] == 2 and status["counts"]["embedding"] == 1 and status["counts"]["vision"] == 1,
            status["counts"],
        )

        persona = client.post(
            f"{BASE}/persona",
            headers=headers,
            json={
                "name": "Ada",
                "persona": "Data analyst",
                "tone": "Direct",
                "response_style": "Bullet points",
                "expertise": "SQL",
                "language": "English",
                "additional_instructions": "Be brief.",
                "chat_model": "mistral:7b",
            },
        )
        check("create persona with agent model", persona.status_code == 200, persona.text[:300])
        check("persona model stored in agent config", persona.json()["persona"].get("chat_model") == "mistral:7b", persona.json()["persona"])

        saved = client.put(f"{BASE}/models/selected", headers=admin, json={"chat_model": "mistral:7b"})
        check("host can select chat model", saved.status_code == 200, saved.text[:300])
        selected = client.get(f"{BASE}/models/selected").json()["selected"]
        check("chat selection changed", selected["chat_model"] == "mistral:7b", selected)
        check("embedding selection unchanged", selected["embedding_model"] == "nomic-embed-text", selected)

        chat = client.post(
            f"{BASE}/chat",
            headers=headers,
            json={"message": "Hello there", "stream": False, "use_documents": False},
        )
        check("chat completes through Ollama API", chat.status_code == 200, chat.text[:300])
        conversation_id = chat.json()["conversation_id"]
        convo = client.get(f"{BASE}/conversations/{conversation_id}", headers=headers).json()["conversation"]
        check(
            "conversation stores user and assistant messages",
            [m["role"] for m in convo["messages"]] == ["user", "assistant"],
            convo["messages"],
        )
        check("agent model used for inference", chat.json()["model"] == "mistral:7b", chat.json().get("model"))

        pdf = Path("/tmp/bf-nightingale.pdf")
        make_pdf(pdf)
        with pdf.open("rb") as handle:
            upload = client.post(
                f"{BASE}/documents/upload",
                headers=headers,
                files={"file": ("nightingale.pdf", handle, "application/pdf")},
            )
        check("PDF upload and indexing", upload.status_code == 200, upload.text[:400])
        document = upload.json()["document"]
        document_id = document["id"]
        check("document stored in data/documents", document.get("file_exists"), document)
        check(
            "document file lives in data/documents",
            (DATA / "documents").exists() and any((DATA / "documents").iterdir()),
            list((DATA / "documents").glob("*")),
        )

        query = client.post(
            f"{BASE}/documents/query",
            headers=headers,
            json={"question": "Who founded modern nursing?"},
        )
        check("document query returns hits", query.status_code == 200, query.text[:300])
        hits = query.json()["results"]
        check(
            "RAG retrieves the relevant Nightingale passage",
            any("Nightingale" in (hit.get("text") or "") for hit in hits),
            [hit.get("text", "")[:80] for hit in hits],
        )

        grounded = client.post(
            f"{BASE}/chat",
            headers=headers,
            json={"message": "Who founded modern nursing?", "stream": False},
        )
        check("chat with RAG succeeds", grounded.status_code == 200, grounded.text[:200])
        check("chat returns document source references", bool(grounded.json().get("sources")), grounded.json().get("sources"))

        check(
            "other workspace cannot read conversation",
            client.get(f"{BASE}/conversations/{conversation_id}", headers=headers_b).status_code == 404,
        )
        check("other workspace cannot see documents", client.get(f"{BASE}/documents", headers=headers_b).json()["documents"] == [])
        check(
            "other workspace cannot delete document",
            client.delete(f"{BASE}/documents/{document_id}", headers=headers_b).status_code == 404,
        )
        check(
            "client cannot change settings",
            client.put(f"{BASE}/settings", headers=headers, json={"chat_history_limit": 5}).status_code == 401,
        )
        check(
            "client cannot restore a backup",
            client.post(f"{BASE}/backup/restore", headers=headers, json={"backup_id": "x.zip"}).status_code == 401,
        )
        check(
            "client cannot pull models",
            client.post(f"{BASE}/models/pull", headers=headers, json={"name": "x", "confirm": True}).status_code == 401,
        )

        backup = client.post(f"{BASE}/backup", headers=admin, json={"include_vectors": True})
        check("backup created", backup.status_code == 200, backup.text[:400])
        backup_id = backup.json()["backup"]["id"]
        check("backup file exists", (DATA / "backups" / backup_id).exists(), backup_id)

        extra = client.post(f"{BASE}/persona", headers=headers, json={"name": "Temporary", "persona": "Test"})
        check("extra persona created before restore", extra.status_code == 200)
        restored = client.post(f"{BASE}/backup/restore", headers=admin, json={"backup_id": backup_id})
        check("backup restore succeeds", restored.status_code == 200, restored.text[:600])
        personas_now = client.get(f"{BASE}/personas", headers=headers).json()["personas"]
        check(
            "restore removes data created after the backup",
            [p["name"] for p in personas_now] == ["Ada"],
            [p["name"] for p in personas_now],
        )
        check(
            "restore keeps the original conversation",
            client.get(f"{BASE}/conversations/{conversation_id}", headers=headers).status_code == 200,
        )

        settings_saved = client.put(
            f"{BASE}/settings", headers=admin, json={"chat_history_limit": 7, "document_top_k": 3}
        )
        check("settings saved", settings_saved.status_code == 200, settings_saved.text[:200])

        before_chunks = client.get(f"{BASE}/health").json()["vector_store"]["chunks"]
        delete = client.delete(f"{BASE}/documents/{document_id}", headers=headers)
        check("document deletion succeeds", delete.status_code == 200, delete.text[:300])
        after_chunks = client.get(f"{BASE}/health").json()["vector_store"]["chunks"]
        check(
            "deleting a document removes its vectors",
            after_chunks < before_chunks,
            f"{before_chunks} -> {after_chunks}",
        )
        orphan = client.post(f"{BASE}/documents/query", headers=headers, json={"question": "Nightingale"})
        check("deleted document is no longer retrievable", orphan.status_code == 404, orphan.text[:200])

        with pdf.open("rb") as handle:
            upload2 = client.post(
                f"{BASE}/documents/upload",
                headers=headers,
                files={"file": ("nightingale-persist.pdf", handle, "application/pdf")},
            )
        check("second PDF uploaded before restart", upload2.status_code == 200, upload2.text[:200])

        stop(app)
        time.sleep(1.5)
        app = start_app("b")
        check("server restarts on the same data", wait_ready(client))

        personas_after = client.get(f"{BASE}/personas", headers=headers).json()["personas"]
        check("persona persists across restart", any(p["name"] == "Ada" for p in personas_after), [p["name"] for p in personas_after])
        convo_after = client.get(f"{BASE}/conversations/{conversation_id}", headers=headers)
        check("conversation persists across restart", convo_after.status_code == 200, convo_after.text[:200])
        selected_after = client.get(f"{BASE}/models/selected").json()["selected"]
        check("model selection persists across restart", selected_after["chat_model"] == "mistral:7b", selected_after)
        settings_after = client.get(f"{BASE}/settings").json()["settings"]
        check(
            "application settings persist across restart",
            settings_after["chat_history_limit"] == 7 and settings_after["document_top_k"] == 3,
            settings_after,
        )
        docs_after = client.get(f"{BASE}/documents", headers=headers).json()["documents"]
        check(
            "document metadata persists across restart",
            any(d["name"] == "nightingale-persist.pdf" for d in docs_after),
            [d["name"] for d in docs_after],
        )
        check(
            "document file still exists after restart",
            all(d["file_exists"] for d in docs_after),
            docs_after,
        )
        rag_after = client.post(f"{BASE}/documents/query", headers=headers, json={"question": "Crimean War"})
        check(
            "RAG still works after restart",
            rag_after.status_code == 200
            and any("Crimean" in (h.get("text") or "") for h in rag_after.json()["results"]),
            rag_after.text[:300],
        )

        write_models(["llama3.2:3b", "nomic-embed-text", "llava"])
        refresh = client.post(f"{BASE}/models/refresh", headers=admin)
        check("model refresh works", refresh.status_code == 200, refresh.text[:300])
        refreshed = refresh.json()["status"]
        check(
            "missing selected model is reported",
            any(m["model"] == "mistral:7b" for m in refreshed["missing"]),
            refreshed["missing"],
        )
        check("missing model warning is shown", bool(refreshed["warning"]), refreshed["warning"])
        blocked = client.post(
            f"{BASE}/chat",
            headers=headers,
            json={"message": "Hello", "stream": False, "use_documents": False},
        )
        check(
            "chat refuses instead of silently switching models",
            blocked.status_code == 409 and "not installed" in blocked.text.lower(),
            blocked.text[:300],
        )

        stop(stub)
        time.sleep(1)
        offline = client.get(f"{BASE}/health")
        check("app stays healthy when Ollama is offline", offline.status_code == 200, offline.text[:200])
        check(
            "offline state is reported",
            offline.json()["ollama"]["connected"] is False and bool(offline.json()["ollama"]["error"]),
            offline.json()["ollama"],
        )
        models_offline = client.get(f"{BASE}/models").json()
        check("model list reports disconnected", models_offline["connected"] is False and bool(models_offline["error"]))
        offline_chat = client.post(f"{BASE}/chat", headers=headers, json={"message": "Hello", "stream": False})
        check(
            "chat returns a friendly offline error",
            offline_chat.status_code == 503 and "not reachable" in offline_chat.text.lower(),
            offline_chat.text[:300],
        )
        check("settings endpoint still works offline", client.get(f"{BASE}/settings").status_code == 200)
        audit = client.get(f"{BASE}/audit", headers=admin)
        check("audit records exist", audit.status_code == 200 and len(audit.json()["audit"]) > 5, audit.text[:200])
        check(
            "audit includes login and document events",
            {"auth.login", "document.upload", "backup.restore"}.issubset(
                {row["action"] for row in audit.json()["audit"]}
            ),
            sorted({row["action"] for row in audit.json()["audit"]}),
        )
        remaining = client.get(f"{BASE}/conversations", headers=headers).json()["conversations"]
        check("conversations not erased", len(remaining) >= 1, len(remaining))
    finally:
        stop(app)
        stop(stub)

    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\n{passed}/{len(results)} checks passed")
    failed = [name for name, ok, _ in results if not ok]
    if failed:
        print("FAILED:", failed)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
