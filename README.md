# Agente - Electiva Tecnologica II

Agente en Python que automatiza el flujo del proyecto:

1. Lleva una bitacora de avance (`bitacora.md`).
2. Le pide a Gemini que redacte la descripcion del proyecto.
3. Crea/usa el repositorio en GitHub y sube los cambios.
4. Despliega el proyecto en GitHub Pages.
5. Genera la pagina web final (`docs/index.html`) con la info del proyecto,
   su propio codigo y el QR que apunta a la pagina ya desplegada.

## Como correrlo

1. Instala dependencias:
   ```
   pip install -r requirements.txt
   ```
2. Abre el archivo `.env` (ya existe en esta carpeta) y pega tu clave de
   Google AI Studio en la linea `GEMINI_API_KEY=` (nunca la pegues en un chat).
3. Verifica con que cuenta de GitHub va a trabajar `gh`:
   ```
   gh auth status
   ```
   Cambia de cuenta activa si hace falta con `gh auth switch --user TU_USUARIO`.
4. Primero una prueba local, sin tocar GitHub:
   ```
   python agent.py --dry-run
   ```
   Abre `docs/index.html` en el navegador para revisar el resultado.
5. Cuando estes listo para publicar de verdad:
   ```
   python agent.py
   ```
   Al final imprime la URL publica de la pagina (GitHub Pages) y dentro de
   `docs/index.html` queda el QR apuntando a esa misma URL.

## Arbol del proceso (Obsidian)

Exporta tu arbol/canvas de Obsidian como imagen y guardala en esta carpeta
como `arbol.png` (o `.jpg`/`.svg`) antes de correr el agente: la pagina la
muestra automaticamente.
