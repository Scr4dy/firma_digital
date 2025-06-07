from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import UploadFile, Form
from fastapi.responses import JSONResponse
from fastapi.responses import RedirectResponse

from datetime import datetime
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography import x509
from cryptography.x509.oid import NameOID
from pathlib import Path


app = FastAPI()

# BASE_DIR apunta ahora a la carpeta 'backend'
BASE_DIR = Path(__file__).resolve().parent

# Ruta de plantillas en el frontend
templates = Jinja2Templates(directory=str(BASE_DIR.parent / "frontend"))

# Ruta de PDFs firmados
SIGNED_PDF_DIR = BASE_DIR / "signed_pdfs"
SIGNED_PDF_DIR.mkdir(exist_ok=True)

EFIRMAS_DIR = BASE_DIR / "efirmas"
EFIRMAS_DIR.mkdir(exist_ok=True)


# Monta carpetas estáticas
app.mount("/frontend", StaticFiles(directory=BASE_DIR.parent / "frontend"), name="frontend")
app.mount("/signed_pdfs", StaticFiles(directory=SIGNED_PDF_DIR), name="signed_pdfs")
app.mount("/efirmas", StaticFiles(directory=EFIRMAS_DIR), name="efirmas")

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

@app.get("/registro_firma", response_class=HTMLResponse)
def formulario_generar(request: Request):
    return templates.TemplateResponse("components/registro_firma.html", {"request": request})

@app.post("/generar_firma", response_class=HTMLResponse)
def generar_firma_digital(
    request: Request,
    nombre: str = Form(...),
    apellidos: str = Form(...),
    fecha_nac: str = Form(...),
    correo: str = Form(...)
):
    # Generar RFC ficticio
    iniciales = (apellidos[:2] + nombre[0]).upper()
    fecha = datetime.strptime(fecha_nac, "%Y-%m-%d").strftime("%y%m%d")
    rfc = f"{iniciales}{fecha}"

    # Crear carpeta para el RFC
    rfc_dir = EFIRMAS_DIR / rfc
    rfc_dir.mkdir(parents=True, exist_ok=True)

    # Generar clave privada
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    key_path = rfc_dir / f"{rfc}.key"
    with open(key_path, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))

    # Generar certificado autofirmado
    subject = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, f"{nombre} {apellidos}"),
        x509.NameAttribute(NameOID.EMAIL_ADDRESS, correo),
    ])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow())
        .not_valid_after(datetime.utcnow().replace(year=datetime.utcnow().year + 1))
        .sign(key, hashes.SHA256())
    )
    cert_path = rfc_dir / f"{rfc}.cer"
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    # Mostrar RFC generado y enlaces de descarga
    return templates.TemplateResponse("components/registro_firma.html", {
        "request": request,
        "mensaje": f"RFC generado exitosamente: {rfc}",
        "descarga_key": f"/efirmas/{rfc}/{rfc}.key",
        "descarga_cer": f"/efirmas/{rfc}/{rfc}.cer",
        "volver_inicio": True
    })
    