import { useEffect, useRef, useState } from 'react'
import './App.css'

// Locally this falls back to your Flask dev server. In production, Vercel
// (or whichever host you use) injects VITE_API_BASE from its dashboard —
// set it to your deployed backend's URL, e.g. https://your-app.onrender.com/api
const API_BASE = "https://ai-memory-assistant-3.onrender.com/api"

export default function App() {
  const [files, setFiles] = useState([])
  const [health, setHealth] = useState(null)
  const [dragOver, setDragOver] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState('')
  const [messages, setMessages] = useState([])
  const [question, setQuestion] = useState('')
  const [asking, setAsking] = useState(false)
  const fileInputRef = useRef(null)
  const chatEndRef = useRef(null)

  const refreshFiles = () => {
    fetch(`${API_BASE}/files`).then(r => r.json()).then(setFiles).catch(() => {})
  }

  useEffect(() => {
    fetch(`${API_BASE}/health`).then(r => r.json()).then(setHealth).catch(() =>
      setHealth({ status: 'unreachable' })
    )
    refreshFiles()
  }, [])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, asking])

  async function handleFiles(fileList) {
    setUploadError('')
    setUploading(true)
    for (const file of fileList) {
      const form = new FormData()
      form.append('file', file)
      try {
        const res = await fetch(`${API_BASE}/upload`, { method: 'POST', body: form })
        const data = await res.json()
        if (!res.ok) throw new Error(data.error || 'Upload failed')
      } catch (err) {
        setUploadError(`${file.name}: ${err.message}`)
      }
    }
    setUploading(false)
    refreshFiles()
    fetch(`${API_BASE}/health`).then(r => r.json()).then(setHealth).catch(() => {})
  }

  function onDrop(e) {
    e.preventDefault()
    setDragOver(false)
    if (e.dataTransfer.files?.length) handleFiles(Array.from(e.dataTransfer.files))
  }

  async function askQuestion() {
    const q = question.trim()
    if (!q || asking) return
    setMessages(m => [...m, { role: 'user', text: q }])
    setQuestion('')
    setAsking(true)
    try {
      const res = await fetch(`${API_BASE}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error || 'Something went wrong')
      setMessages(m => [...m, { role: 'assistant', text: data.answer, sources: data.sources }])
    } catch (err) {
      setMessages(m => [...m, { role: 'error', text: err.message }])
    }
    setAsking(false)
  }

  const noKey = health && health.has_api_key === false
  const unreachable = health && health.status === 'unreachable'

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">Re</span>
          <div className="brand-text">
            <h1>Recall</h1>
            <p>AI Digital Memory Assistant</p>
          </div>
        </div>
        <div className={`status-pill ${unreachable ? 'status-bad' : noKey ? 'status-warn' : 'status-good'}`}>
          {unreachable
            ? 'Backend not running'
            : noKey
              ? 'No Gemini API key set'
              : `${health?.chunks_stored ?? 0} memory chunks indexed`}
        </div>
      </header>

      <div className="layout">
        <aside className="sidebar">
          <div
            className={`dropzone ${dragOver ? 'dropzone-active' : ''}`}
            onDragOver={e => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              multiple
              hidden
              accept=".pdf,.png,.jpg,.jpeg,.webp,.bmp,.txt,.md"
              onChange={e => e.target.files?.length && handleFiles(Array.from(e.target.files))}
            />
            <p className="dropzone-title">Drop files to remember</p>
            <p className="dropzone-hint">PDF · Image (OCR) · Note (.txt/.md)</p>
            {uploading && <p className="dropzone-status">Reading and indexing…</p>}
          </div>

          {uploadError && <p className="upload-error">{uploadError}</p>}

          <div className="file-list">
            <p className="file-list-label">Indexed files ({files.length})</p>
            {files.length === 0 && <p className="empty-note">Nothing uploaded yet.</p>}
            {files.map(f => (
              <div className="card-stub" key={f.filename}>
                <span className="card-stub-name">{f.filename}</span>
                <span className="card-stub-meta">{f.chunks} chunk{f.chunks === 1 ? '' : 's'}</span>
              </div>
            ))}
          </div>
        </aside>

        <main className="chat">
          {messages.length === 0 && (
            <div className="chat-empty">
              <p className="chat-empty-title">Ask about anything you've uploaded</p>
              <p className="chat-empty-hint">
                "What time is my dentist appointment?" · "What did the contract say about
                the deposit?" · "Summarize my meeting notes from last week."
              </p>
            </div>
          )}

          <div className="chat-log">
            {messages.map((m, i) => (
              <div key={i} className={`bubble bubble-${m.role}`}>
                <p>{m.text}</p>
                {m.sources && m.sources.length > 0 && (
                  <div className="sources">
                    <p className="sources-label">Recalled from</p>
                    <div className="sources-row">
                      {m.sources.map((s, j) => (
                        <div className="source-card" key={j}>
                          <span className="source-file">{s.filename}</span>
                          <span className="source-snippet">{s.snippet}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}
            {asking && <div className="bubble bubble-assistant bubble-loading">Searching your memory…</div>}
            <div ref={chatEndRef} />
          </div>

          <div className="composer">
            <input
              type="text"
              placeholder="Ask a question about your files…"
              value={question}
              onChange={e => setQuestion(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && askQuestion()}
            />
            <button onClick={askQuestion} disabled={asking || !question.trim()}>
              Ask
            </button>
          </div>
        </main>
      </div>
    </div>
  )
}
