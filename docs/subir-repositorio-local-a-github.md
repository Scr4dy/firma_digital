# Como subir un proyecto local a github.

## Autor original: https://github.com/cgonzalezdai

Desde la web de github

Creamos un nuevo repositorio en https://github.com. 

Le damos nombre, descripción, seleccionamos si va a ser un proyecto publico o privado si es el caso, y dejamos el check de crear README sin marcar. Le damos a crear repositorio y con esto ya tenemos el repositorio donde alojaremos nuestro proyecto.

desde la terminal del equipo donde esta el proyecto que queremos subir a github
Nos vamos a la carpeta del proyecto y ejecutamos estos comandos.

```
git init

git add .

git commit -m "first commit"

git remote add origin https://github.com/NOMBRE_USUARIO/NOMBRE_PROYECTO.git

git push -u origin main
```

