from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import UploadFile, Form
from fastapi.responses import JSONResponse

from pathlib import Path
import os

app = FastAPI()

# BASE_DIR apunta ahora a la carpeta 'backend'
BASE_DIR = Path(__file__).resolve().parent

# Ruta de plantillas en el frontend
templates = Jinja2Templates(directory=str(BASE_DIR.parent / "frontend"))

# Ruta de PDFs firmados
SIGNED_PDF_DIR = BASE_DIR / "signed_pdfs"
SIGNED_PDF_DIR.mkdir(exist_ok=True)

# Monta carpetas estáticas
app.mount("/frontend", StaticFiles(directory=BASE_DIR.parent / "frontend"), name="frontend")
app.mount("/signed_pdfs", StaticFiles(directory=SIGNED_PDF_DIR), name="signed_pdfs")

@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/documentos", response_class=HTMLResponse)
def ver_documentos(request: Request, rfc: str = "usuario123"):
    """Carga los documentos firmados para el RFC proporcionado"""
    user_dir = SIGNED_PDF_DIR / rfc
    user_dir.mkdir(parents=True, exist_ok=True)

    archivos = [
        {"nombre": f.name, "ruta": f"/signed_pdfs/{rfc}/{f.name}"}
        for f in user_dir.glob("*.pdf")
    ]
    return templates.TemplateResponse("documento.html", {"request": request, "archivos": archivos, "rfc": rfc})

@app.get("/descargar/{rfc}/{archivo}", response_class=FileResponse)
def descargar_pdf(rfc: str, archivo: str):
    ruta = SIGNED_PDF_DIR / rfc / archivo
    if ruta.exists():
        return FileResponse(ruta, filename=archivo, media_type='application/pdf')
    return HTMLResponse("<h2>Archivo no encontrado</h2>", status_code=404)

@app.post("/subir_pdf")
async def subir_pdf(rfc: str = Form(...), archivo: UploadFile = Form(...)):
    """Guarda un archivo PDF firmado para un usuario (RFC)"""
    if not archivo.filename.endswith(".pdf"): # type: ignore
        return JSONResponse(status_code=400, content={"mensaje": "Solo se permiten archivos PDF."})

    user_dir = SIGNED_PDF_DIR / rfc
    user_dir.mkdir(parents=True, exist_ok=True)

    destino = user_dir / archivo.filename # type: ignore
    with open(destino, "wb") as buffer:
        buffer.write(await archivo.read())

    return JSONResponse(status_code=200, content={"mensaje": "PDF subido exitosamente.", "archivo": archivo.filename})