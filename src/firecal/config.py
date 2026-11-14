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
DATOS_REPO_DIR = _ruta("DATOS_REPO_DIR", RAIZ.parent / "aivital-incendios-datos")  # clon del repo público de datos
DATOS_URL_BASE = "https://marcelo-corro.github.io/aivital-incendios-datos"

FIRMS_MAP_KEY = os.getenv("FIRMS_MAP_KEY", "").strip()
