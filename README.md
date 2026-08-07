# Recall — AI Digital Memory Assistant

Upload PDFs, images, and notes. Ask questions in plain English. Get answers
pulled from your own files, with the source shown.

**How it works:** each file is parsed to text (PDF parsing / OCR for images),
split into chunks, and embedded with Google's Gemini embedding model. A
question is embedded the same way, compared against every chunk with cosine
similarity, and the closest chunks are handed to Gemini to write the final
answer — this pattern is called RAG (Retrieval-Augmented Generation).

## 1. Get a free Gemini API key

1. Go to **https://aistudio.google.com/apikey**
2. Sign in with any Google account → **Create API key**
3. Copy it — free tier, no credit card needed

## 2. Set up the backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Open `.env` and paste your key:
```
GEMINI_API_KEY=your_real_key_here
```

**Also install Tesseract OCR** (needed for reading images — not a Python
package, a system program):
- macOS: `brew install tesseract`
- Ubuntu/Debian/WSL: `sudo apt install tesseract-ocr`
- Windows: installer at https://github.com/UB-Mannheim/tesseract/wiki

Run the backend:
```bash
python app.py
```
It should print `Running on http://127.0.0.1:5000`. Leave this terminal open.

## 3. Set up the frontend

In a **new terminal**:
```bash
cd frontend
npm install
npm run dev
```
Open the URL it prints (usually **http://localhost:5173**).

## 4. Try it

1. Drag a PDF, a photo of a note, or a `.txt` file into the drop zone.
2. Wait for it to appear under "Indexed files."
3. Ask a question about it in plain English.
4. The answer appears with the source file(s) it was pulled from.

## Troubleshooting

| Problem | Fix |
|---|---|
| "Backend not running" pill | Make sure `python app.py` is still running and printed no errors |
| "No Gemini API key set" | Check `.env` is in `backend/` (not `backend/backend/`) and has no quotes around the key |
| Upload fails with "No text could be extracted" | For scanned images, use a clear, well-lit, in-focus photo — blurry handwriting will fail OCR |
| `tesseract is not installed` error | Install Tesseract (see step 2) — it's a separate program, not `pip install`-able |
| CORS error in browser console | Confirm the backend is on port 5000 — `API_BASE` in `frontend/src/App.jsx` expects `http://localhost:5000/api` |

## Demo tips

- Upload 2–3 files *before* your presentation (a PDF syllabus, a photo of
  handwritten notes, a screenshot) so you're not waiting on OCR live.
- Ask a question whose answer isn't a literal keyword match — e.g. if a note
  says "pushed the call to 4," ask "when's the call now?" — this is what
  shows off semantic search over plain keyword search (Ctrl+F).
- Have one question ready where the answer draws from a specific file, so you
  can point at the "Recalled from" source card and explain the retrieval step.

## Deploying it live (free)

Two pieces to deploy: the Flask **backend** (as a Docker web service, so
Tesseract OCR installs correctly) and the React **frontend** (as a static
site). Render + Vercel are used below — both have free tiers, no credit card.

### A. Push the code to GitHub first

Both hosts deploy from a GitHub repo.

```bash
cd ai-memory-assistant
git init
git add .
git commit -m "Initial commit"
```
Create a new empty repo on github.com, then:
```bash
git remote add origin https://github.com/<your-username>/<repo-name>.git
git branch -M main
git push -u origin main
```

### B. Deploy the backend on Render

1. Go to **render.com** → sign up/in with GitHub → **New → Web Service**
2. Pick your repo. Render should detect the `Dockerfile` — if it asks for a
   runtime, choose **Docker**.
3. Set **Root Directory** to `backend`.
4. Under **Environment Variables**, add:
   - `GEMINI_API_KEY` = your real key
   - `ALLOWED_ORIGIN` = leave blank for now, you'll set it after step C
5. Click **Create Web Service**. First build takes a few minutes (it's
   installing Tesseract inside the container).
6. Once live, copy the URL Render gives you, e.g.
   `https://ai-memory-assistant.onrender.com`.

*Free-tier notes:* the instance sleeps after inactivity (first request after
a while takes ~30s to wake up), and the local `store.json`/`uploads/` reset
on redeploy since free disks aren't persistent — fine for a class demo, not
for production.

### C. Deploy the frontend on Vercel

1. Go to **vercel.com** → sign up/in with GitHub → **Add New → Project**
2. Import the same repo.
3. Set **Root Directory** to `frontend`. Vercel auto-detects Vite.
4. Under **Environment Variables**, add:
   - `VITE_API_BASE` = `https://ai-memory-assistant.onrender.com/api`
     (your Render URL from step B, + `/api`)
5. Click **Deploy**. You'll get a URL like `https://your-app.vercel.app`.

### D. Connect them

Go back to Render → your backend service → **Environment** → set
`ALLOWED_ORIGIN` = `https://your-app.vercel.app` (your Vercel URL, no
trailing slash) → save (this redeploys automatically).

Now open your Vercel URL — that's your live site.

### Running with Docker locally (optional, matches production exactly)

```bash
cd backend
docker build -t memory-backend .
docker run -p 5000:5000 --env-file .env memory-backend
```

## Project structure

```
ai-memory-assistant/
├── backend/
│   ├── app.py              # Flask API: upload, query, file list
│   ├── requirements.txt
│   ├── Dockerfile          # for deploying with Tesseract included
│   ├── .env.example
│   └── uploads/            # saved files (created at runtime)
└── frontend/
    ├── src/
    │   ├── App.jsx          # main UI: upload + chat
    │   ├── App.css
    │   └── main.jsx
    ├── .env.example
    └── index.html
```
