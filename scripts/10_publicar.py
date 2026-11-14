"""Paso 10 del pipeline (B): publica public/ en GitHub Pages (repo aivital-incendios-datos).

Copia PUBLIC_DIR al clon local del repo de datos (DATOS_REPO_DIR), hace commit y, si no se pide lo contrario,
push. Antes verifica que manifest.json diga "ejemplo": false. Después espera a que Pages sirva el nuevo manifest.

Uso:
    python scripts/10_publicar.py --sin-push   # copia y hace commit local; revisar antes de subir
    python scripts/10_publicar.py              # copia, commit, push y verifica la URL
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import requests  # noqa: E402

from firecal import config  # noqa: E402
from firecal.export.publicar import PublicacionError, sincronizar, verificar_destino, verificar_origen  # noqa: E402


def git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8", check=False)
    if r.returncode != 0:
        raise PublicacionError(f"git {' '.join(args)} falló:\n{r.stderr.strip()}")
    return r.stdout.strip()


def esperar_pages(generado_utc: str, intentos: int = 16, espera_s: int = 15) -> bool:
    url = f"{config.DATOS_URL_BASE}/manifest.json"
    for n in range(1, intentos + 1):
        try:
            actual = requests.get(url, timeout=20, headers={"Cache-Control": "no-cache"}).json().get("generado_utc")
        except (requests.RequestException, ValueError):
            actual = None
        if actual == generado_utc:
            return True
        print(f"  ({n}/{intentos}) Pages todavía sirve generado_utc={actual}; espero {espera_s} s…")
        time.sleep(espera_s)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sin-push", action="store_true", help="solo copia y hace commit local")
    args = parser.parse_args()

    publico, repo = config.PUBLIC_DIR, config.DATOS_REPO_DIR
    try:
        manifest = verificar_origen(publico)
        verificar_destino(repo)
        if git(repo, "status", "--porcelain"):
            raise PublicacionError(f"{repo} tiene cambios sin commitear; revísalos antes de publicar.")
        git(repo, "pull", "--ff-only")

        sincronizar(publico, repo)
        git(repo, "add", "-A")
        if not git(repo, "status", "--porcelain"):
            print("Sin cambios respecto de lo ya publicado. Nada que hacer.")
            return 0
        git(repo, "commit", "-m", f"datos {datetime.now():%Y-%m-%d %H:%M}")
        print(f"Commit hecho en {repo}:")
        print(git(repo, "show", "--stat", "--format=%h %s", "HEAD").splitlines()[0])

        if args.sin_push:
            print("--sin-push: revisa el commit y haz `git push` cuando quieras.")
            return 0

        git(repo, "push")
    except PublicacionError as e:
        print(f"No se publicó: {e}")
        return 1

    print(f"Push hecho. Esperando a que Pages sirva {config.DATOS_URL_BASE}/manifest.json …")
    if esperar_pages(manifest["generado_utc"]):
        print("Listo: Pages ya sirve los datos nuevos. Avisa a José y actualiza 'Estado actual' en el README de datos.")
        return 0
    print("Pages aún no refleja el cambio (puede tardar unos minutos más). Revisa la URL a mano.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
