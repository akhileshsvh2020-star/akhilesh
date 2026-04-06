import os
import tempfile
import asyncio
import logging
from io import BytesIO
from PIL import Image

from fastapi import FastAPI, File, UploadFile, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader

from dotenv import load_dotenv
import fitz  # PyMuPDF
from docx import Document
from google import genai

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("pdf2word")

# ── Load environment variables from .env ──────────────────────────────────────
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
API_SECRET_KEY = os.getenv("API_SECRET_KEY")
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")]
HOST            = os.getenv("HOST", "0.0.0.0")
PORT            = int(os.getenv("SERVER_PORT", os.getenv("PORT", "8000")))
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
MAX_PAGE_COUNT   = int(os.getenv("MAX_PAGE_COUNT", "100"))

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not set. Create backend/.env and add your key.")
if not API_SECRET_KEY or API_SECRET_KEY == "change-me-before-deploying-use-secrets-token-urlsafe":
    logger.warning("⚠️  API_SECRET_KEY is using the default placeholder — change it in .env before deploying!")

# ── Gemini AI client ───────────────────────────────────────────────────────────
client = genai.Client(api_key=GEMINI_API_KEY)
logger.info("Gemini AI client initialised (model: gemini-2.0-flash)")

# ── FastAPI app ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="PDF2Word API",
    description="Converts PDF pages to Word documents with LaTeX equation extraction via Gemini AI.",
    version="1.1.0",
    # Disable auto-generated docs in prod — set DOCS_ENABLED=true in .env to re-enable
    docs_url="/docs" if os.getenv("DOCS_ENABLED", "false").lower() == "true" else None,
    redoc_url=None,
)

# ── CORS — locked to explicit origins only ─────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,       # ✅ No longer wildcard *
    allow_methods=["POST", "OPTIONS"],   # Only what we actually need
    allow_headers=["Content-Type", "X-API-Key"],
    allow_credentials=False,
)
logger.info(f"CORS allowed origins: {ALLOWED_ORIGINS}")

# ── Auth — API Key via header ──────────────────────────────────────────────────
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(api_key: str = Depends(api_key_header)):
    """
    Validates X-API-Key header on every protected endpoint.
    Returns 401 for missing key, 403 for wrong key.
    """
    if not api_key:
        logger.warning("Request rejected — missing X-API-Key header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Provide X-API-Key header.",
        )
    if api_key != API_SECRET_KEY:
        logger.warning("Request rejected — invalid API key")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key.",
        )
    return api_key

# ── Per-page AI processing ─────────────────────────────────────────────────────
async def process_page_async(page_num: int, pdf_path: str, prompt: str, semaphore: asyncio.Semaphore):
    """Render a single PDF page to JPEG and send it to Gemini for transcription."""
    async with semaphore:
        try:
            pdf_document = fitz.open(pdf_path)
            page = pdf_document.load_page(page_num)
            # 1x scale @ JPEG quality 65 — readable by AI, ~44% smaller payload
            matrix = fitz.Matrix(1.0, 1.0)
            pix    = page.get_pixmap(matrix=matrix, alpha=False)
            img_data = pix.tobytes("jpeg", jpg_quality=65)
            pdf_document.close()
        except Exception as e:
            logger.error(f"Page {page_num + 1}: Failed to render PDF — {e}")
            return page_num, f"\n[Render Error on Page {page_num + 1}: {e}]\n"

        img = Image.open(BytesIO(img_data))

        for attempt in range(5):
            try:
                response = await client.aio.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=[prompt, img],
                )
                logger.info(f"Page {page_num + 1}: OK (attempt {attempt + 1})")
                return page_num, response.text.strip()

            except Exception as e:
                error_str = str(e).lower()

                if "429" in error_str or "quota" in error_str or "rate" in error_str:
                    logger.warning(f"Page {page_num + 1}: Rate limited — sleeping 65s (attempt {attempt + 1})")
                    await asyncio.sleep(65)
                    continue

                if attempt == 4:
                    logger.error(f"Page {page_num + 1}: Failed after 5 attempts — {e}")
                    return page_num, f"\n[AI Processing Error on Page {page_num + 1}: {e}]\n"

                wait = 2 ** attempt
                logger.warning(f"Page {page_num + 1}: Error on attempt {attempt + 1}, retrying in {wait}s — {e}")
                await asyncio.sleep(wait)

# ── /convert endpoint ──────────────────────────────────────────────────────────
@app.post(
    "/convert",
    summary="Convert a PDF to a Word document with LaTeX equations",
    dependencies=[Depends(verify_api_key)],   # ✅ Auth required
)
async def convert_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    # ── Input validation ──────────────────────────────────────────────────────
    if file.content_type not in ("application/pdf",) and not file.filename.lower().endswith(".pdf"):
        logger.warning(f"Rejected upload — not a PDF: {file.filename} ({file.content_type})")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only PDF files are accepted.",
        )

    # Read file into memory to check size before writing to disk
    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        logger.warning(f"Rejected upload — file too large: {size_mb:.1f} MB > {MAX_FILE_SIZE_MB} MB")
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {MAX_FILE_SIZE_MB} MB.",
        )

    logger.info(f"Processing upload: {file.filename} ({size_mb:.2f} MB)")

    # Write to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
        tmp_pdf.write(contents)
        pdf_path = tmp_pdf.name

    docx_path = pdf_path.replace(".pdf", "_latex.docx")

    try:
        pdf_document  = fitz.open(pdf_path)
        total_pages   = len(pdf_document)
        pdf_document.close()

        # ── Page count guard ──────────────────────────────────────────────────
        if total_pages > MAX_PAGE_COUNT:
            os.remove(pdf_path)
            logger.warning(f"Rejected — too many pages: {total_pages} > {MAX_PAGE_COUNT}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"PDF has {total_pages} pages — maximum allowed is {MAX_PAGE_COUNT}.",
            )

        logger.info(f"Starting AI translation: {total_pages} pages — {file.filename}")

        # Shorter prompt = fewer tokens = faster + cheaper
        prompt = (
            "Transcribe this page exactly. Wrap all math/equations in LaTeX delimiters ($...$ or $$...$$). "
            "Preserve spacing and structure. Output plain text + LaTeX only — no markdown code blocks."
        )

        # 10 concurrent requests — gemini-2.0-flash free tier is 15 RPM, so 10 is safe
        semaphore = asyncio.Semaphore(10)
        tasks     = [
            process_page_async(page_num, pdf_path, prompt, semaphore)
            for page_num in range(total_pages)
        ]
        results = await asyncio.gather(*tasks)
        results = sorted(results, key=lambda x: x[0])

        # ── Build DOCX ────────────────────────────────────────────────────────
        doc = Document()
        for idx, (page_num, text) in enumerate(results):
            text  = text.strip()
            lines = text.split("\n")
            if lines and lines[0].strip().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

            doc.add_paragraph(text)
            if idx < total_pages - 1:
                doc.add_page_break()

        doc.save(docx_path)
        out_filename = file.filename.replace(".pdf", "_latex.docx")
        logger.info(f"Conversion complete — {out_filename}")

        # Cleanup temp files once the response is sent
        background_tasks.add_task(os.remove, pdf_path)
        background_tasks.add_task(os.remove, docx_path)

        return FileResponse(
            path=docx_path,
            filename=out_filename,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    except HTTPException:
        # Re-raise our own validation errors without wrapping them
        raise

    except Exception as e:
        # Cleanup on unexpected error
        logger.error(f"Unexpected error during conversion of {file.filename}: {e}", exc_info=True)
        for path in (pdf_path, docx_path):
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during conversion. Please try again.",
        )

# ── Health check (unauthenticated — for uptime monitors) ──────────────────────
@app.get("/health", include_in_schema=False)
async def health():
    return {"status": "ok", "model": "gemini-2.0-flash"}

# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api:app",
        host=HOST,
        port=PORT,
        reload=os.getenv("RELOAD", "false").lower() == "true",
        log_level="info",
    )
