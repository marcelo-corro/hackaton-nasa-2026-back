"""Publicación en GitHub Pages (tarea B4): copia `public/` al clon del repo de datos.

Este módulo solo prepara la carpeta (verifica y sincroniza); el commit y el push los hace
`scripts/10_publicar.py`. Funciones sin red.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

# Lo que vive en el repo de datos y no se genera. `.github` guarda la actualización diaria (GitHub Actions): si se
# borrara al publicar, la automatización se eliminaría a sí misma en su primera corrida.
CONSERVAR = {"README.md", ".nojekyll", ".git", ".github"}


class PublicacionError(RuntimeError):
    """No se puede publicar: el mensaje explica por qué y qué hacer."""


def verificar_origen(publico: Path) -> dict:
    """Comprueba que `publico` tenga un manifest con datos reales y lo devuelve."""
    ruta = publico / "manifest.json"
    if not ruta.exists():
        raise PublicacionError(f"No existe {ruta}. Corre antes scripts/09_exportar.py.")
    manifest = json.loads(ruta.read_text(encoding="utf-8"))
    if manifest.get("ejemplo") is not False:
        raise PublicacionError('manifest.json no dice "ejemplo": false: no se publican datos de ejemplo como reales.')
    if not (publico / "index.html").exists():
        raise PublicacionError(
            "Falta public/index.html (sin él la URL base da 404). Vuelve a correr scripts/09_exportar.py."
        )
    esperados = len(manifest.get("regiones", []))
    for carpeta in ("calendario", "focos"):
        presentes = len(list((publico / carpeta).glob("*"))) if (publico / carpeta).is_dir() else 0
        if presentes != esperados:
            raise PublicacionError(
                f"public/{carpeta} tiene {presentes} archivos y el manifest lista {esperados} comunas: "
                "vuelve a correr scripts/09_exportar.py."
            )
    return manifest


def verificar_destino(repo: Path) -> None:
    """Comprueba que `repo` sea un clon de git (no una carpeta cualquiera que se vaya a vaciar)."""
    if not (repo / ".git").exists():
        raise PublicacionError(
            f"{repo} no es un clon de hackaton-nasa-2026-datos. Clónalo ahí o apunta DATOS_REPO_DIR en .env."
        )


def sincronizar(publico: Path, repo: Path) -> None:
    """Deja `repo` igual a `publico`, salvo README.md, .nojekyll, .git y .github, que se conservan."""
    verificar_destino(repo)
    for item in repo.iterdir():
        if item.name in CONSERVAR:
            continue
        shutil.rmtree(item) if item.is_dir() else item.unlink()
    for item in publico.iterdir():
        destino = repo / item.name
        shutil.copytree(item, destino) if item.is_dir() else shutil.copy2(item, destino)
    (repo / ".nojekyll").touch()
