"""
Agente para la Electiva Tecnologica II.

Funciones que cumple este agente:
  1. Llevar una bitacora de avance del proyecto (bitacora.md).
  2. Consultar a Gemini (API de Google AI Studio) para redactar la
     descripcion del proyecto.
  3. Inicializar el repositorio, crearlo en GitHub y subir los cambios.
  4. Desplegar el proyecto en GitHub Pages.
  5. Generar la pagina web final (docs/index.html) con la informacion
     del proyecto y su propio script.
  6. Generar el codigo QR que apunta a la pagina ya desplegada.

Uso:
    python agent.py            -> ejecuta el flujo completo
    python agent.py --dry-run  -> genera la pagina localmente, sin git/GitHub
    python agent.py --chat     -> habla con el agente (Gemma) por terminal
"""

import argparse
import html
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs"
BITACORA = ROOT / "bitacora.md"
AGENT_SOURCE = Path(__file__)
TREE_IMAGE_CANDIDATES = ["arbol.png", "arbol.jpg", "arbol.svg"]

load_dotenv(ROOT / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemma-4-26b-a4b-it")
DEFAULT_DESCRIPTION = (
    "Este proyecto conecta un arbol de proceso construido en Obsidian "
    "con un agente que automatiza el registro de avances, la subida a "
    "GitHub, el despliegue en GitHub Pages y la generacion de esta pagina."
)
GITHUB_REPO_NAME = os.getenv("GITHUB_REPO_NAME", "agente-electiva-tecnologica")
REPO_VISIBILITY = os.getenv("REPO_VISIBILITY", "public")
DESCRIPTION_PROMPT = (
    "Redacta en un parrafo (maximo 60 palabras) la descripcion de un "
    "proyecto universitario que conecta un arbol de proceso hecho en "
    "Obsidian con un agente automatizado en Python que registra avances, "
    "sube el proyecto a GitHub, lo despliega en GitHub Pages y genera "
    "una pagina con su propio codigo y un QR."
)
EXTRA_STYLE = ""
_client = None


def get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def log(message: str) -> None:
    """Registra un avance en bitacora.md y lo imprime en consola."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    line = f"- **{timestamp}** {message}\n"
    if not BITACORA.exists():
        BITACORA.write_text("# Bitacora del agente\n\n", encoding="utf-8")
    with BITACORA.open("a", encoding="utf-8") as f:
        f.write(line)
    print(f"[bitacora] {message}")


def run_cmd(cmd: list[str], cwd: Path = ROOT, check: bool = True) -> str:
    """Ejecuta un comando de shell y devuelve su salida."""
    result = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, shell=False
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Fallo el comando {' '.join(cmd)}:\n{result.stdout}\n{result.stderr}"
        )
    return result.stdout.strip()


def ask_gemini(prompt: str) -> str:
    """Envia un prompt a Gemma (via el SDK google-genai) y devuelve el texto de respuesta."""
    if not GEMINI_API_KEY:
        log("No hay GEMINI_API_KEY configurada, se usa texto por defecto.")
        return DEFAULT_DESCRIPTION

    try:
        client = get_client()
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=prompt)],
                ),
            ],
        )
        return response.text.strip()
    except Exception as exc:
        log(f"Fallo la llamada a Gemma ({exc}), se usa texto por defecto.")
        return DEFAULT_DESCRIPTION


def ensure_git_repo() -> None:
    if not (ROOT / ".git").exists():
        run_cmd(["git", "init"])
        run_cmd(["git", "branch", "-M", "main"])
        log("Repositorio git inicializado.")


def ensure_github_remote() -> str:
    """Crea el repo en GitHub (si no existe) y devuelve el usuario dueno."""
    try:
        run_cmd(["git", "remote", "get-url", "origin"])
        log("El remoto 'origin' ya existe.")
    except RuntimeError:
        visibility_flag = "--public" if REPO_VISIBILITY == "public" else "--private"
        run_cmd(
            [
                "gh", "repo", "create", GITHUB_REPO_NAME,
                visibility_flag, "--source=.", "--remote=origin",
            ]
        )
        log(f"Repositorio '{GITHUB_REPO_NAME}' creado en GitHub.")

    owner = run_cmd(["gh", "api", "user", "-q", ".login"])
    return owner


def commit_and_push(message: str) -> None:
    run_cmd(["git", "add", "-A"])
    diff = run_cmd(["git", "diff", "--cached", "--name-only"], check=False)
    if not diff:
        log("No hay cambios nuevos para commitear.")
        return
    run_cmd(["git", "commit", "-m", message])
    run_cmd(["git", "push", "-u", "origin", "main"])
    log(f"Cambios subidos a GitHub: {message}")


def enable_github_pages(owner: str) -> str:
    """Activa GitHub Pages sirviendo la carpeta docs/ y devuelve la URL final."""
    repo_path = f"repos/{owner}/{GITHUB_REPO_NAME}/pages"
    try:
        run_cmd(["gh", "api", "-X", "POST", repo_path,
                  "-f", "source[branch]=main", "-f", "source[path]=/docs"])
        log("GitHub Pages activado (POST).")
    except RuntimeError:
        try:
            run_cmd(["gh", "api", "-X", "PUT", repo_path,
                      "-f", "source[branch]=main", "-f", "source[path]=/docs"])
            log("GitHub Pages actualizado (PUT).")
        except RuntimeError as exc:
            log("No se pudo activar Pages automaticamente, hazlo manual en "
                "Settings > Pages (branch: main, carpeta: /docs).")
            print(exc)

    return f"https://{owner}.github.io/{GITHUB_REPO_NAME}/"


def find_tree_image() -> str | None:
    for name in TREE_IMAGE_CANDIDATES:
        if (ROOT / name).exists():
            return name
    return None


def strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    return text.strip()


REQUIRED_PLACEHOLDERS = ["%%AGENT_SOURCE%%", "%%BITACORA%%"]


def generate_html_with_ai(description: str, tree_image: str | None,
                           qr_relpath: str | None, page_url: str | None) -> str | None:
    """Le pide a Gemma que redacte y arme la pagina web completa."""
    tree_instruction = (
        f'Incluye la imagen con <img src="{tree_image}" alt="Arbol del proceso">.'
        if tree_image else
        "Todavia no hay imagen del arbol: escribe un aviso pidiendo exportar "
        "el arbol de Obsidian como arbol.png."
    )
    qr_instruction = (
        f'Incluye la imagen con <img src="{qr_relpath}" alt="QR de esta pagina"> '
        "y despues un enlace visible <a href=\"%%PAGE_URL%%\">%%PAGE_URL%%</a> "
        "(deja el texto %%PAGE_URL%% tal cual, sin traducirlo ni cambiarlo)."
        if qr_relpath else
        "El QR todavia no existe: escribe que se genera despues del primer despliegue."
    )

    prompt = f"""Eres el propio agente de software de un proyecto universitario y
debes redactar tu pagina web de presentacion en un unico archivo HTML.

Devuelve UNICAMENTE el codigo HTML completo (empezando en <!doctype html>),
sin explicaciones, sin comentarios y sin usar bloques de markdown (```).

Requisitos del documento:
- Idioma: espanol. Titulo de la pestana: "Agente - Electiva Tecnologica II".
- CSS dentro de un <style> en el <head>, sin librerias ni CDNs externos.
- Diseno limpio y profesional, responsive, con buen contraste de color.
- Debe tener estas secciones, en este orden, cada una con su <h2>:
  1. "Descripcion del proyecto": redacta un par de parrafos amigables a partir
     de esta idea: {description}
  2. "Arbol del proceso (Obsidian)": {tree_instruction}
  3. "Bitacora de avance": dentro de un <pre>, incluye exactamente y sin
     modificar el siguiente texto literal (no lo traduzcas ni resumas):
     %%BITACORA%%
  4. "Script del agente (agent.py)": dentro de <pre><code>, incluye exactamente
     y sin modificar el siguiente texto literal (no lo traduzcas ni reescribas):
     %%AGENT_SOURCE%%
  5. "QR de esta pagina": {qr_instruction}
{f'Instrucciones de estilo pedidas por el usuario (siguelas de verdad): {EXTRA_STYLE}' if EXTRA_STYLE else ''}

Los textos %%BITACORA%%, %%AGENT_SOURCE%% y %%PAGE_URL%% son marcadores que un
programa reemplazara despues: cópialos tal cual, exactamente una vez cada uno,
en el lugar que corresponda."""

    raw = ask_gemini(prompt)
    if raw == DEFAULT_DESCRIPTION:
        return None

    raw = strip_code_fences(raw)
    if not all(p in raw for p in REQUIRED_PLACEHOLDERS):
        log("La pagina generada por Gemma no incluyo los marcadores esperados, se usa la plantilla de respaldo.")
        return None
    return raw


def build_static_fallback(description: str, tree_image: str | None,
                           qr_relpath: str | None, page_url: str | None,
                           source_code: str, bitacora_text: str) -> str:
    tree_section = (
        f'<img src="{tree_image}" alt="Arbol del proceso" class="tree-img">'
        if tree_image else
        "<p>(Coloca aqui un export de tu arbol de Obsidian como "
        "<code>arbol.png</code> en la raiz del proyecto y vuelve a correr el agente.)</p>"
    )
    qr_section = (
        f'<img src="{qr_relpath}" alt="QR de esta pagina" class="qr-img">'
        f'<p><a href="{page_url}">{page_url}</a></p>'
        if qr_relpath and page_url else
        "<p>El QR se genera despues del primer despliegue.</p>"
    )
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Agente - Electiva Tecnologica II</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 900px; margin: 40px auto;
         padding: 0 20px; line-height: 1.6; color: #1a1a1a; }}
  h1, h2 {{ color: #10467a; }}
  pre {{ background: #0d1117; color: #c9d1d9; padding: 16px; overflow-x: auto;
         border-radius: 8px; font-size: 13px; }}
  .tree-img, .qr-img {{ max-width: 320px; display: block; margin: 12px 0; }}
  section {{ margin-bottom: 40px; }}
</style>
</head>
<body>
<h1>Agente de la Electiva Tecnologica II</h1>

<section>
<h2>Descripcion del proyecto</h2>
<p>{html.escape(description)}</p>
</section>

<section>
<h2>Arbol del proceso (Obsidian)</h2>
{tree_section}
</section>

<section>
<h2>Bitacora de avance</h2>
<pre>{bitacora_text}</pre>
</section>

<section>
<h2>Script del agente (agent.py)</h2>
<pre><code>{source_code}</code></pre>
</section>

<section>
<h2>QR de esta pagina</h2>
{qr_section}
</section>

</body>
</html>
"""


def build_site(description: str, page_url: str | None, qr_relpath: str | None) -> None:
    """Le pide a la IA que genere docs/index.html; si falla, usa una plantilla fija."""
    DOCS.mkdir(exist_ok=True)

    source_code = html.escape(AGENT_SOURCE.read_text(encoding="utf-8"))
    bitacora_text = (
        html.escape(BITACORA.read_text(encoding="utf-8"))
        if BITACORA.exists() else "Aun no hay entradas."
    )
    tree_image = find_tree_image()
    if tree_image:
        shutil.copy(ROOT / tree_image, DOCS / tree_image)

    html_content = generate_html_with_ai(description, tree_image, qr_relpath, page_url)
    if html_content is not None:
        html_content = html_content.replace("%%AGENT_SOURCE%%", source_code)
        html_content = html_content.replace("%%BITACORA%%", bitacora_text)
        html_content = html_content.replace("%%PAGE_URL%%", page_url or "")
        log("Pagina generada por Gemma.")
    else:
        html_content = build_static_fallback(
            description, tree_image, qr_relpath, page_url, source_code, bitacora_text
        )
        log("Pagina generada con la plantilla de respaldo (sin IA).")

    (DOCS / "index.html").write_text(html_content, encoding="utf-8")
    log("Pagina web guardada en docs/index.html.")


def generate_qr(url: str) -> str:
    import qrcode
    img = qrcode.make(url)
    img.save(DOCS / "qr.png")
    log(f"QR generado apuntando a {url}.")
    return "qr.png"


def get_owner() -> str:
    return run_cmd(["gh", "api", "user", "-q", ".login"])


def run_deploy_pipeline() -> str:
    """Corre el flujo completo: describe, sube a GitHub, despliega y genera el QR."""
    description = ask_gemini(DESCRIPTION_PROMPT)
    ensure_git_repo()
    owner = ensure_github_remote()
    build_site(description, page_url=None, qr_relpath=None)
    commit_and_push("Actualiza el agente y la pagina")
    page_url = enable_github_pages(owner)
    qr_relpath = generate_qr(page_url)
    build_site(description, page_url=page_url, qr_relpath=qr_relpath)
    commit_and_push("Agrega/actualiza el QR de la pagina desplegada")
    return page_url


def cambiar_estilo_pagina(instrucciones_de_estilo: str) -> str:
    """Cambia el estilo visual de la pagina web del proyecto (colores, tipografia,
    disposicion, modernidad, etc.) y la regenera en docs/index.html.

    Usa esta funcion cuando el usuario pida que la pagina se vea distinta,
    mas moderna, con otro estilo, otros colores, etc. Esto NO sube los
    cambios a GitHub por si solo; si el usuario tambien pidio publicar o
    desplegar, llama ademas a desplegar_en_github.

    Args:
        instrucciones_de_estilo: descripcion en lenguaje natural de como debe
            verse la pagina.
    """
    global EXTRA_STYLE
    EXTRA_STYLE = instrucciones_de_estilo
    description = ask_gemini(DESCRIPTION_PROMPT)
    has_git = (ROOT / ".git").exists()
    page_url = compute_page_url_if_deployed() if has_git else None
    qr_relpath = "qr.png" if (DOCS / "qr.png").exists() else None
    build_site(description, page_url=page_url, qr_relpath=qr_relpath)
    return "Actualice el estilo de la pagina en docs/index.html."


def desplegar_en_github() -> str:
    """Sube el proyecto a GitHub (creando el repo si hace falta) y publica o
    actualiza la pagina en GitHub Pages, con su QR.

    Usa esta funcion cuando el usuario pida subir, publicar, desplegar o
    actualizar la pagina en linea.
    """
    page_url = run_deploy_pipeline()
    return f"Despliegue completado. La pagina esta publicada en: {page_url}"


def compute_page_url_if_deployed() -> str | None:
    try:
        run_cmd(["git", "remote", "get-url", "origin"])
    except RuntimeError:
        return None
    return f"https://{get_owner()}.github.io/{GITHUB_REPO_NAME}/"


def chat() -> None:
    """Modo interactivo: habla con el agente (Gemma) desde la terminal.

    El agente puede ademas EJECUTAR acciones reales (no solo responder texto)
    usando function calling: cambiar el estilo de la pagina y desplegarla.
    """
    if not GEMINI_API_KEY:
        print("Configura GEMINI_API_KEY en .env antes de usar el chat.")
        return

    client = get_client()
    chat_session = client.chats.create(
        model=GEMINI_MODEL,
        config=types.GenerateContentConfig(
            system_instruction=(
                "Eres el agente de un proyecto universitario de la Electiva "
                "Tecnologica II. Conoces tu propio codigo (agent.py): llevas "
                "una bitacora de avance, subes el proyecto a GitHub, lo "
                "despliegas en GitHub Pages y generas la pagina web del "
                "proyecto con su QR. Tienes herramientas de verdad para "
                "cambiar el estilo de la pagina y para desplegarla: cuando "
                "el usuario pida algo de eso, LLAMA a la herramienta en vez "
                "de solo decir que lo hiciste. Responde en espanol, breve y claro."
            ),
            tools=[cambiar_estilo_pagina, desplegar_en_github],
        ),
    )
    print("Chat con el agente (escribe 'salir' para terminar).\n")
    while True:
        try:
            user_input = input("Tu: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if user_input.lower() in {"salir", "exit", "quit"}:
            break
        if not user_input:
            continue
        print("Agente: (trabajando... puede tardar 30-60s si toca llamar a la "
              "IA y a GitHub, no cierres la terminal)")
        try:
            response = chat_session.send_message(user_input)
            text = response.text.strip()
        except Exception as exc:
            text = f"(Error al contactar a Gemma: {exc})"
        print(f"Agente: {text}\n")
        log(f"Chat - Usuario dijo: {user_input}")
        log(f"Chat - Agente respondio: {text}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                         help="Genera la pagina localmente sin tocar git/GitHub.")
    parser.add_argument("--chat", action="store_true",
                         help="Habla con el agente por terminal, en vez de correr el flujo completo.")
    args = parser.parse_args()

    if args.chat:
        chat()
        return

    log("Inicio de ejecucion del agente.")

    if args.dry_run:
        description = ask_gemini(DESCRIPTION_PROMPT)
        build_site(description, page_url=None, qr_relpath=None)
        print("\nListo (dry-run). Abre docs/index.html en tu navegador.")
        return

    page_url = run_deploy_pipeline()
    print(f"\nListo. En unos minutos tu pagina estara en: {page_url}")


if __name__ == "__main__":
    main()
