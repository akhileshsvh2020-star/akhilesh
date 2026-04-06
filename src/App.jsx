import { useState, useRef } from 'react';
import { UploadCloud, FileText, CheckCircle, Loader2, ArrowRight, AlertCircle } from 'lucide-react';
import './App.css';

// ── Config from Vite env vars ────────────────────────────────────────────────
// These are set in .env at the project root (never committed to git)
const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || `http://${window.location.hostname}:8000`;
const API_KEY     = import.meta.env.VITE_API_KEY     || '';

function App() {
  const [file,        setFile]        = useState(null);
  const [isDragging,  setIsDragging]  = useState(false);
  const [status,      setStatus]      = useState('idle'); // idle | parsing | done | error
  const [progress,    setProgress]    = useState(0);
  const [statusText,  setStatusText]  = useState('');
  const [errorMsg,    setErrorMsg]    = useState('');

  const fileInputRef = useRef(null);

  // ── Drag & Drop handlers ────────────────────────────────────────────────────
  const handleDragOver  = (e) => { e.preventDefault(); setIsDragging(true);  };
  const handleDragLeave = (e) => { e.preventDefault(); setIsDragging(false); };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files?.length > 0) validateAndSetFile(e.dataTransfer.files[0]);
  };

  const handleFileChange = (e) => {
    if (e.target.files?.length > 0) validateAndSetFile(e.target.files[0]);
  };

  const validateAndSetFile = (selectedFile) => {
    if (selectedFile.type !== 'application/pdf' && !selectedFile.name.toLowerCase().endsWith('.pdf')) {
      setErrorMsg('Please upload a valid PDF document.');
      setFile(null);
      return;
    }
    const maxMB = 50;
    if (selectedFile.size > maxMB * 1024 * 1024) {
      setErrorMsg(`File is too large. Maximum size is ${maxMB} MB.`);
      setFile(null);
      return;
    }
    setErrorMsg('');
    setFile(selectedFile);
    setStatus('idle');
    setProgress(0);
  };

  // ── Animated progress faker ─────────────────────────────────────────────────
  // Smoothly increments the bar while the backend works, stops short of 90%
  // so the jump to 100% only happens once the real response arrives.
  const startFakeProgress = () => {
    let current = 20;
    const tick = () => {
      current += Math.random() * 3;         // random small increments
      const capped = Math.min(current, 88); // never goes past 88% while waiting
      setProgress(capped);
      if (capped < 88) setTimeout(tick, 600 + Math.random() * 400);
    };
    setTimeout(tick, 800);
  };

  // ── Conversion request ──────────────────────────────────────────────────────
  const processPDF = async () => {
    if (!file) return;

    setStatus('parsing');
    setProgress(20);
    setStatusText('Uploading to AI engine — this can take a minute for large files…');
    setErrorMsg('');

    startFakeProgress();

    try {
      if (!API_KEY) {
        throw new Error('VITE_API_KEY is not set in your .env file. The API key is required.');
      }

      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch(`${BACKEND_URL}/convert`, {
        method: 'POST',
        body: formData,
        headers: {
          'X-API-Key': API_KEY,   // ✅ Auth header sent on every request
        },
      });

      if (response.status === 401) throw new Error('Authentication failed — check VITE_API_KEY in your .env file.');
      if (response.status === 403) throw new Error('Invalid API key — make sure frontend and backend .env keys match.');
      if (response.status === 413) throw new Error('File is too large. Please try a smaller PDF.');
      if (response.status === 422) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body?.detail || 'Invalid file — only PDFs are accepted.');
      }
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body?.detail || `Server error (${response.status}). Please try again.`);
      }

      setProgress(95);
      setStatusText('Processing complete! Preparing download…');

      const blob    = await response.blob();
      const outName = file.name.replace(/\.pdf$/i, '_latex.docx');

      setProgress(100);

      // Trigger browser download
      const url = window.URL.createObjectURL(blob);
      const a   = document.createElement('a');
      a.href     = url;
      a.download = outName;
      a.click();
      window.URL.revokeObjectURL(url);

      setTimeout(() => {
        setStatus('done');
        setStatusText('Extraction Complete!');
      }, 500);

    } catch (err) {
      console.error('[PDF2Word]', err);
      setStatus('error');
      setErrorMsg(err.message || 'An unknown error occurred. Please try again.');
      setProgress(0);
    }
  };

  // ── Reset ───────────────────────────────────────────────────────────────────
  const handleRestart = () => {
    setFile(null);
    setStatus('idle');
    setProgress(0);
    setStatusText('');
    setErrorMsg('');
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div className="app-container">
      <header className="header">
        <h1>Extractor<span style={{ color: 'var(--primary)' }}>Pro</span></h1>
        <p>
          Instantly convert huge PDFs into organised Word documents — with every
          equation extracted as editable LaTeX, page by page.
        </p>
      </header>

      <main className="converter-card">
        {/* ── Idle: drop zone ── */}
        {status === 'idle' && (
          <div
            id="drop-zone"
            className={`drop-zone ${isDragging ? 'active' : ''}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            role="button"
            tabIndex={0}
            aria-label="Upload PDF — click or drag and drop"
            onKeyDown={(e) => e.key === 'Enter' && fileInputRef.current?.click()}
          >
            <input
              id="file-input"
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              accept="application/pdf"
              aria-hidden="true"
            />
            <div className="drop-content">
              {file ? (
                <>
                  <FileText className="upload-icon" aria-hidden="true" />
                  <div className="filename">{file.name}</div>
                  <p style={{ color: 'var(--text-muted)' }}>Click to select a different file</p>
                </>
              ) : (
                <>
                  <UploadCloud className="upload-icon" aria-hidden="true" />
                  <h2>Drag &amp; Drop your PDF here</h2>
                  <p>Or click to browse from your computer</p>
                  <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: '0.5rem' }}>
                    Max 50 MB · Max 100 pages
                  </p>
                </>
              )}
            </div>
          </div>
        )}

        {/* ── Parsing: progress ── */}
        {status === 'parsing' && (
          <div className="flex flex-col gap-6 w-full items-center py-8">
            <Loader2 className="upload-icon spin" aria-label="Processing…" />
            <div className="w-full">
              <div className="progress-container mb-4" role="progressbar" aria-valuenow={Math.round(progress)} aria-valuemin={0} aria-valuemax={100}>
                <div className="progress-bar" style={{ width: `${progress}%` }} />
              </div>
              <div className="status-text">{statusText}</div>
            </div>
          </div>
        )}

        {/* ── Done ── */}
        {status === 'done' && (
          <div className="flex flex-col gap-6 w-full items-center py-8">
            <CheckCircle
              className="upload-icon"
              style={{ color: 'var(--success)', width: 80, height: 80 }}
              aria-label="Success"
            />
            <h2 style={{ fontSize: '2rem' }}>Success!</h2>
            <p style={{ color: 'var(--text-muted)', textAlign: 'center' }}>
              Your file has been downloaded as a Word document.<br />
              You can now manually apply MathType or equation formatting.
            </p>
          </div>
        )}

        {/* ── Error banner ── */}
        {errorMsg && (
          <div className="error-msg" role="alert" aria-live="assertive">
            <AlertCircle size={18} style={{ flexShrink: 0 }} aria-hidden="true" />
            {errorMsg}
          </div>
        )}

        {/* ── Action buttons ── */}
        <div className="actions">
          {status === 'idle' && (
            <button
              id="start-btn"
              className="btn"
              disabled={!file}
              onClick={processPDF}
              aria-disabled={!file}
            >
              Start Extraction <ArrowRight size={20} aria-hidden="true" />
            </button>
          )}

          {status === 'done' && (
            <button id="restart-btn" className="btn btn-success" onClick={handleRestart}>
              Convert Another File
            </button>
          )}

          {status === 'error' && (
            <button id="retry-btn" className="btn" onClick={handleRestart}>
              Try Again
            </button>
          )}
        </div>
      </main>
    </div>
  );
}

export default App;
