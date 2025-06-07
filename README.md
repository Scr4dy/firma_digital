# Creación de entorno virtual (Opcional)
Es necesario estar una ruta anterior al proyecto
```
py -m venv firma_digital
```
Acceder a la ruta del proyecto
```
cd firma_digital
```

Activar entorno virtual
```
.\Scripts\activate
```


# Instalación de herramientas Python
```
pip install -r requirements.txt
```


# Paquete de desarrollo con Node.js

### Instalación de paquetes
```
npm install
```

### Ejecución de TailwindCSS (Opcional)
```
npx @tailwindcss/cli -i ./frontend/styles/input.css -o ./frontend/styles/index.css --watch
```

# Ejecución de servidor
```
fastapi dev .\backend\main.py
```