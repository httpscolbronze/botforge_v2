"""Minimal Ollama-compatible stub used ONLY by the automated tests.

It implements /api/version, /api/tags, /api/ps, /api/chat, /api/pull and a
deliberately unavailable /api/embed (so the labelled local embedding fallback
is exercised). It is never imported by the BotForge application and it is not
a substitute for real Ollama inference.
"""

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODELS_FILE = os.environ.get("STUB_MODELS_FILE", "/tmp/bf-stub-models.json")
PORT = int(os.environ.get("STUB_PORT", "11455"))


def models():
    try:
        with open(MODELS_FILE) as handle:
            return json.load(handle)
    except Exception:
        return ["llama3.2:3b", "nomic-embed-text", "llava", "mistral:7b"]


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def _json(self, payload, status=200):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/version":
            self._json({"version": "0.0.0-test"})
        elif self.path == "/api/tags":
            self._json(
                {
                    "models": [
                        {
                            "name": name,
                            "size": 2_000_000_000,
                            "modified_at": "2026-01-01T00:00:00Z",
                            "details": {
                                "family": "llama",
                                "parameter_size": "3B",
                                "quantization_level": "Q4_K_M",
                            },
                        }
                        for name in models()
                    ]
                }
            )
        elif self.path == "/api/ps":
            self._json({"models": []})
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw or b"{}")
        except Exception:
            payload = {}

        if self.path in ("/api/embed", "/api/embeddings"):
            self._json({"error": "embedding disabled in stub"}, 404)
            return

        if self.path == "/api/chat":
            text = "Stub answer: the retrieved context mentions Nightingale."
            if payload.get("stream"):
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson")
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                for piece in (text[:20], text[20:]):
                    line = json.dumps({"message": {"content": piece}, "done": False}) + "\n"
                    data = line.encode()
                    self.wfile.write(f"{len(data):X}\r\n".encode() + data + b"\r\n")
                    self.wfile.flush()
                done = (json.dumps({"done": True}) + "\n").encode()
                self.wfile.write(f"{len(done):X}\r\n".encode() + done + b"\r\n")
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()
            else:
                self._json({"message": {"role": "assistant", "content": text}, "done": True})
            return

        if self.path == "/api/pull":
            body = "".join(
                json.dumps(line) + "\n"
                for line in ({"status": "pulling manifest"}, {"status": "success"})
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path == "/api/generate":
            self._json({"response": "", "done": True})
            return

        self._json({"error": "not found"}, 404)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
