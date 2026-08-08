"""
AI Digital Memory Assistant — backend
--------------------------------------
Ingests PDFs, images (via OCR) and text notes, embeds them with the
Gemini embedding model, stores the vectors locally, and answers
natural-language questions by retrieving the most relevant chunks and
asking Gemini to answer using only that context (a small RAG pipeline).
"""
import json
import os
import time
import uuid
from pathlib import Path

import numpy as np
import pdfplumber
import pytesseract
import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from PIL import Image

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
EMBED_MODEL = os.environ.get("GEMINI_EMBED_MODEL", "gemini-embedding-001")
CHAT_MODEL = os.environ.get("GEMINI_CHAT_MODEL", "gemini-2.5-flash")
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

APP_DIR = Path(__file__).parent
UPLOAD_DIR = APP_DIR / "uploads"
STORE_PATH = APP_DIR / "store.json"
UPLOAD_DIR.mkdir(exist_ok=True)

CHUNK_SIZE = 900       # characters per chunk
CHUNK_OVERLAP = 150    # characters shared between consecutive chunks
TOP_K_DEFAULT = 4

app = Flask(__name__)

# In dev, the Vite server runs on a different port, so CORS must allow it.
# In production, set ALLOWED_ORIGIN to your deployed frontend's URL (e.g.
# https://your-app.vercel.app). "*" is used only if nothing is set, which is
# fine for a quick demo but not for a real production app.
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "*")
CORS(app, origins=[ALLOWED_ORIGIN] if ALLOWED_ORIGIN != "*" else "*")


# --------------------------------------------------------------------------
# Local vector store (a JSON file — no external DB needed for a class demo)
# --------------------------------------------------------------------------
def load_store():
    if STORE_PATH.exists():
        with open(STORE_PATH, "r") as f:
            raw = json.load(f)
        for item in raw:
            item["embedding"] = np.array(item["embedding"], dtype=np.float32)
        return raw
    return []


def save_store(store):
    serializable = []
    for item in store:
        copy = dict(item)
        copy["embedding"] = item["embedding"].tolist()
        serializable.append(copy)
    with open(STORE_PATH, "w") as f:
        json.dump(serializable, f)


STORE = load_store()


# --------------------------------------------------------------------------
# File ingestion
# --------------------------------------------------------------------------
def extract_text(filepath, filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext == "pdf":
        parts = []
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                parts.append(page.extract_text() or "")
        return "\n".join(parts)

    if ext in ("png", "jpg", "jpeg", "webp", "bmp"):
        image = Image.open(filepath)
        return pytesseract.image_to_string(image)

    if ext in ("txt", "md"):
        with open(filepath, "r", errors="ignore") as f:
            return f.read()

    raise ValueError(f"Unsupported file type: .{ext or 'unknown'}")


def chunk_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    text = text.strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start:start + size])
        start += size - overlap
    return chunks


# --------------------------------------------------------------------------
# Gemini calls (embeddings + generation)
# --------------------------------------------------------------------------
def require_api_key():
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Add it to backend/.env (see .env.example)."
        )


def embed_text(text, task_type="RETRIEVAL_DOCUMENT"):
    require_api_key()
    url = f"{GEMINI_BASE}/{EMBED_MODEL}:embedContent"
    payload = {
        "content": {"parts": [{"text": text[:8000]}]},
        "taskType": task_type,
    }
    resp = requests.post(url, params={"key": GEMINI_API_KEY}, json=payload, timeout=30)
    resp.raise_for_status()
    return np.array(resp.json()["embedding"]["values"], dtype=np.float32)


def generate_answer(prompt):
    require_api_key()
    url = f"{GEMINI_BASE}/{CHAT_MODEL}:generateContent"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    resp = requests.post(url, params={"key": GEMINI_API_KEY}, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


def cosine_sim(a, b):
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom else 0.0


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "has_api_key": bool(GEMINI_API_KEY),
        "chunks_stored": len(STORE),
    })


@app.route("/api/files", methods=["GET"])
def list_files():
    files = {}
    for item in STORE:
        f = files.setdefault(item["filename"], {
            "filename": item["filename"],
            "chunks": 0,
            "uploaded_at": item["uploaded_at"],
        })
        f["chunks"] += 1
    return jsonify(sorted(files.values(), key=lambda x: x["uploaded_at"], reverse=True))


@app.route("/api/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400

    filename = file.filename
    save_path = UPLOAD_DIR / f"{uuid.uuid4().hex}_{filename}"
    file.save(save_path)

    try:
        text = extract_text(save_path, filename)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    if not text.strip():
        return jsonify({
            "error": "No text could be extracted from this file. If it's a scanned "
                     "image, make sure it's clear and well-lit; tesseract OCR needs "
                     "readable text."
        }), 400

    chunks = chunk_text(text)
    try:
        for chunk in chunks:
            embedding = embed_text(chunk, task_type="RETRIEVAL_DOCUMENT")
            STORE.append({
                "id": uuid.uuid4().hex,
                "filename": filename,
                "text": chunk,
                "embedding": embedding,
                "uploaded_at": time.time(),
            })
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    except requests.HTTPError as e:
        return jsonify({"error": f"Gemini API error: {e.response.text}"}), 502

    save_store(STORE)
    return jsonify({
        "filename": filename,
        "chunks_added": len(chunks),
        "preview": text.strip()[:300],
    })


@app.route("/api/query", methods=["POST"])
def query():
    data = request.get_json(force=True) or {}
    question = data.get("question", "").strip()
    top_k = int(data.get("top_k", TOP_K_DEFAULT))

    if not question:
        return jsonify({"error": "Question is required"}), 400
    if not STORE:
        return jsonify({"error": "No documents uploaded yet — add a file first."}), 400

    try:
        q_embedding = embed_text(question, task_type="RETRIEVAL_QUERY")
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    except requests.HTTPError as e:
        return jsonify({"error": f"Gemini API error: {e.response.text}"}), 502

    scored = sorted(
        ((cosine_sim(q_embedding, item["embedding"]), item) for item in STORE),
        key=lambda x: x[0],
        reverse=True,
    )
    top = scored[:top_k]

    context = "\n\n".join(f"[Source: {item['filename']}]\n{item['text']}" for _, item in top)
    prompt = (
        "You are a personal memory assistant. Answer the question using ONLY the "
        "context below, which was pulled from the user's own uploaded files. If the "
        "answer isn't in the context, say you couldn't find it in their files — "
        "never make something up.\n\n"
        f"CONTEXT:\n{context}\n\n"
        f"QUESTION: {question}\n\n"
        "Give a clear, direct answer, then note which file(s) it came from."
    )

    try:
        answer = generate_answer(prompt)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    except requests.HTTPError as e:
        return jsonify({"error": f"Gemini API error: {e.response.text}"}), 502

    sources = [
        {"filename": item["filename"], "score": round(score, 3), "snippet": item["text"][:220]}
        for score, item in top
    ]
    return jsonify({"answer": answer, "sources": sources})


@app.route("/api/reset", methods=["POST"])
def reset():
    STORE.clear()
    save_store(STORE)
    for f in UPLOAD_DIR.glob("*"):
        f.unlink()
    return jsonify({"status": "cleared"})


if __name__ == "__main__":
    # Render (and most hosts) inject the port to bind to via $PORT.
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
    @app.route("/")
    def home():
        return :"Working Perfectly"
    @app.route ("/test")
    def test():
        return "Test route working"