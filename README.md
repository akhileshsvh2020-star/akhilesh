# ExtractorPro — PDF to Word with LaTeX Equations

Convert large PDFs into structured Word documents (.docx), with every mathematical equation automatically extracted as editable LaTeX — powered by Google Gemini AI.

---

## What It Does

- Upload a PDF (up to 50 MB / 100 pages)
- Each page is rendered and sent to Gemini AI for transcription
- All math/equations are wrapped in LaTeX delimiters (`$...$` / `$$...$$`)
- Plain text and structure are preserved
- Downloads a ready-to-use `.docx` file

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19 + Vite 8 |
| Backend | Python 3.10+ · FastAPI · Uvicorn |
| AI | Google Gemini 2.0 Flash (`google-genai`) |
| PDF rendering | PyMuPDF (`fitz`) |
| Word output | python-docx |

---

## Prerequisites

- **Node.js** 18+ and **npm**
- **Python** 3.10+
- A **Google Gemini API key** — get one free at [aistudio.google.com](https://aistudio.google.com/app/apikey)

---

## Installation & Setup

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd pdf2excel_web
```

### 2. Configure the backend

```bash
cd backend
copy .env.example .env    # Windows
# cp .env.example .env    # macOS/Linux
```

Open `backend/.env` and fill in:

```env
GEMINI_API_KEY=your-google-gemini-api-key-here
API_SECRET_KEY=your-long-random-secret-here     # generate one below
ALLOWED_ORIGINS=http://localhost:5173
```

Generate a secure `API_SECRET_KEY`:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Install Python dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 4. Configure the frontend

```bash
cd ..   # back to project root
copy .env.example .env    # Windows
# cp .env.example .env    # macOS/Linux
```

Open `.env` and set:

```env
VITE_API_KEY=your-long-random-secret-here   # must exactly match API_SECRET_KEY above
VITE_BACKEND_URL=http://localhost:8000
```

### 5. Install Node dependencies

```bash
npm install
```

---

## Running Locally

### Windows — one click

Double-click **`start.bat`** in the project root. It will:
- Install missing Python packages
- Validate both `.env` files exist
- Start the backend on `http://localhost:8000`
- Start the frontend on `http://localhost:5173`
- Open the app in your browser

### Manual start

**Terminal 1 — Backend:**
```bash
cd backend
python api.py
```

**Terminal 2 — Frontend:**
```bash
npm run dev
```

Then open [http://localhost:5173](http://localhost:5173).

---

## Environment Variables Reference

### `backend/.env`

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | ✅ | Your Google Gemini API key |
| `API_SECRET_KEY` | ✅ | Shared secret for frontend↔backend auth |
| `ALLOWED_ORIGINS` | ✅ | Comma-separated list of allowed frontend URLs |
| `HOST` | optional | Bind address (default: `0.0.0.0`) |
| `PORT` | optional | Port (default: `8000`) |
| `MAX_FILE_SIZE_MB` | optional | Upload size limit (default: `50`) |
| `MAX_PAGE_COUNT` | optional | Page count limit (default: `100`) |
| `DOCS_ENABLED` | optional | Set `true` to enable `/docs` Swagger UI |
| `RELOAD` | optional | Set `true` to enable hot-reload (dev only) |

### `.env` (frontend)

| Variable | Required | Description |
|---|---|---|
| `VITE_API_KEY` | ✅ | Must match `API_SECRET_KEY` in backend |
| `VITE_BACKEND_URL` | ✅ | URL of the running backend |

---

## API Endpoints

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/convert` | X-API-Key | Upload a PDF, receive a `.docx` |
| `GET` | `/health` | None | Uptime check — returns `{"status":"ok"}` |

---

## Known Limitations

- **Free Gemini tier**: 15 requests per minute. Large PDFs (10+ pages) will automatically slow down with retry/backoff logic built in.
- **Equations are LaTeX text** inside the Word document — not rendered MathType objects. You can use MathType or similar tools to render them post-conversion.
- **Accuracy depends on PDF quality**: Scanned/low-resolution PDFs may produce less accurate transcriptions.

---

## Project Structure

```
pdf2excel_web/
├── backend/
│   ├── api.py              # FastAPI backend (all conversion logic)
│   ├── requirements.txt    # Python dependencies
│   ├── .env                # Backend secrets (never commit)
│   └── .env.example        # Template for setup
├── src/
│   ├── App.jsx             # Main React component
│   ├── App.css             # Component styles
│   └── index.css           # Global design tokens
├── .env                    # Frontend secrets (never commit)
├── .env.example            # Template for setup
├── .gitignore
├── start.bat               # Windows one-click launcher
├── vite.config.js
└── package.json
```

---

## Security Notes

- `.env` files are listed in `.gitignore` and must **never** be committed
- The `API_SECRET_KEY` / `VITE_API_KEY` pair provides basic auth — keep it secret
- CORS is restricted to the origins listed in `ALLOWED_ORIGINS`
- Swagger UI (`/docs`) is disabled by default in production
