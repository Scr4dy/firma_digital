from fastapi import FastAPI, Request, UploadFile, Cookie, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.x509 import load_pem_x509_certificate

from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

import zipfile
import json
import bcrypt

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# BASE_DIR apunta ahora a la carpeta 'backend'
BASE_DIR = Path(__file__).resolve().parent

# Ruta de plantillas en el frontend
templates = Jinja2Templates(directory=str(BASE_DIR.parent / "frontend"))

# Ruta de PDFs firmados
SIGNED_PDF_DIR = BASE_DIR / "signed_pdfs"
SIGNED_PDF_DIR.mkdir(exist_ok=True)

# Ruta de eFirmas
EFIRMAS_DIR = BASE_DIR / "efirmas"
EFIRMAS_DIR.mkdir(exist_ok=True)

# Ruta de usuarios
USUARIOS_DIR = BASE_DIR / "usuarios"
USUARIOS_DIR.mkdir(exist_ok=True)

# Cargar archivo .env
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

# Montar directorios estáticos
app.mount("/frontend", StaticFiles(directory=BASE_DIR.parent / "frontend"), name="frontend")
app.mount("/signed_pdfs", StaticFiles(directory=SIGNED_PDF_DIR), name="signed_pdfs")
app.mount("/efirmas", StaticFiles(directory=EFIRMAS_DIR), name="efirmas")

@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/documentos", response_class=HTMLResponse)
def ver_documentos(request: Request, session_rfc: str = Cookie(default=None)):
    if not session_rfc:
        return RedirectResponse(url="/", status_code=303)

    user_dir = SIGNED_PDF_DIR / session_rfc
    user_dir.mkdir(parents=True, exist_ok=True)

    archivos = [
        {"nombre": f.name, "ruta": f"/signed_pdfs/{session_rfc}/{f.name}"}
        for f in user_dir.glob("*.pdf")
    ]
    return templates.TemplateResponse("components/documento.html", {"request": request, "archivos": archivos, "rfc": session_rfc})

@app.post("/auth/login")
async def login(
    rfc: str = Form(...),
    cer_file: UploadFile = Form(...),
    key_file: UploadFile = Form(...),
    password: str = Form(...),
):
    
    # Validar existencia del usuario
    user_file = USUARIOS_DIR / f"{rfc}.json"
    if not user_file.exists():
        return JSONResponse(status_code=401, content={"mensaje": "Usuario no registrado."})

    with open(user_file, "r", encoding="utf-8") as f:
        user_data = json.load(f)

    # Validar contraseña
    if not bcrypt.checkpw(password.encode(), user_data["password_hash"].encode()):
        return JSONResponse(status_code=401, content={"mensaje": "Contraseña incorrecta."})

    # Guardar archivos temporales
    temp_dir = BASE_DIR / "temp"
    temp_dir.mkdir(exist_ok=True)
    cer_path = temp_dir / f"{rfc}.cer"
    key_path = temp_dir / f"{rfc}.key"

    with open(cer_path, "wb") as f:
        f.write(await cer_file.read())
    with open(key_path, "wb") as f:
        f.write(await key_file.read())

    # Validar que la clave privada puede abrirse con la contraseña
    try:
        with open(key_path, "rb") as key_file_obj:
            private_key = serialization.load_pem_private_key(
                key_file_obj.read(),
                password=password.encode()
            )
    except Exception as e:
        return JSONResponse(status_code=401, content={"mensaje": f"Clave privada inválida o contraseña incorrecta."})

    # (Opcional) Validar que el .key coincide con el certificado
    try:
        with open(cer_path, "rb") as cert_file_obj:
            cert = load_pem_x509_certificate(cert_file_obj.read())
            public_key = cert.public_key()

        # Validar que ambas claves coinciden
        if public_key.public_numbers() != private_key.public_key().public_numbers(): # type: ignore
            return JSONResponse(status_code=401, content={"mensaje": "El certificado no corresponde con la clave privada."})
    except Exception as e:
        return JSONResponse(status_code=400, content={"mensaje": "Error al verificar el certificado."})

    response = JSONResponse(status_code=200, content={"mensaje": f"Autenticación exitosa para {rfc}."})
    response.set_cookie(key="session_rfc", value=rfc, httponly=True)
    return response


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
    correo: str = Form(...),
    password: str = Form(...)
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
            encryption_algorithm=serialization.BestAvailableEncryption(password.encode())
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

    zip_path = rfc_dir / f"{rfc}_firma.zip"
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        zipf.write(key_path, arcname=f"{rfc}.key")
        zipf.write(cert_path, arcname=f"{rfc}.cer")

    # Encriptar la contraseña
    hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    # Guardar info del usuario
    registro = {
        "rfc": rfc,
        "nombre": nombre,
        "apellidos": apellidos,
        "correo": correo,
        "password_hash": hashed_password
    }

    with open(USUARIOS_DIR / f"{rfc}.json", "w", encoding="utf-8") as f:
        json.dump(registro, f, indent=2, ensure_ascii=False)

    return templates.TemplateResponse("components/registro_firma.html", {
        "request": request,
        "mensaje": f"RFC generado exitosamente: {rfc}",
        "descarga_key": f"/efirmas/{rfc}/{rfc}.key",
        "descarga_cer": f"/efirmas/{rfc}/{rfc}.cer",
        "descarga_zip": f"/efirmas/{rfc}/{rfc}_firma.zip",
        "volver_inicio": True
    })

@app.get("/logout")
def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("session_rfc")
    return response