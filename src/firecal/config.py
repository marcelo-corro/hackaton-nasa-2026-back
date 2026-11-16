"""Rutas y configuración leídas desde .env (ver .env.example)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[2]
load_dotenv(RAIZ / ".env")


def _ruta(variable: str, defecto: Path) -> Path:
    valor = os.getenv(variable, "").strip()
    return Path(valor).expanduser() if valor else defecto


DATA_DIR = RAIZ / "data"
FIRMS_RAW_DIR = _ruta("FIRMS_RAW_DIR", DATA_DIR / "raw" / "firms")
COMUNAS_SHP = DATA_DIR / "raw" / "comunas" / "comunas.shp"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
PUBLIC_DIR = _ruta("PUBLIC_DIR", RAIZ / "public")
# Clon del repo público de datos: el nombre actual o, si no está, la carpeta con el nombre anterior (renombrado el 16-11-2026)
DATOS_REPO_DIR = _ruta("DATOS_REPO_DIR", next((p for p in (RAIZ.parent / "hackaton-nasa-2026-datos", RAIZ.parent / "aivital-incendios-datos")
                                              if p.exists()), RAIZ.parent / "hackaton-nasa-2026-datos"))
DATOS_URL_BASE = "https://marcelo-corro.github.io/hackaton-nasa-2026-datos"

FIRMS_MAP_KEY = os.getenv("FIRMS_MAP_KEY", "").strip()
