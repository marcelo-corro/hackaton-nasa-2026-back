"""Controles antes de publicar sola (actualización diaria en GitHub Actions).

Si algún control falla, la corrida termina con error y no se publica nada: los datos de ayer siguen en línea y GitHub
avisa por correo. Son funciones puras sobre la carpeta public/ para poder probarlas.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

N_COMUNAS = 345
RIESGO = ("riesgo/ultimo.json", "riesgo/48h.json", "riesgo/7d.json")
DIAS_MAX_ATRASO = 2   # el riesgo es para "hoy": se acepta hasta 2 días de atraso si FIRMS se demora
DIAS_AVISO_CLIMA = 7  # NASA POWER llega con ~3 días de rezago; más de una semana es raro y se avisa


def _leer(publico: Path, ruta: str) -> dict | None:
    p = publico / ruta
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def controles_publicacion(publico: Path, hoy: date, version: str, llave: str = "") -> tuple[list[str], list[str]]:
    """Devuelve (errores, avisos). Con algún error no se publica.

    `hoy`: fecha de Chile del día de la corrida. `version`: contrato esperado. `llave`: la MAP_KEY de FIRMS, que no
    puede aparecer en ningún archivo publicado.
    """
    errores: list[str] = []
    avisos: list[str] = []

    m = _leer(publico, "manifest.json")
    if m is None:
        return ["falta manifest.json"], avisos
    if m.get("ejemplo") is not False:
        errores.append('manifest.json no dice "ejemplo": false')
    if m.get("contrato") != version:
        errores.append(f"contrato {m.get('contrato')!r} distinto del esperado {version!r}")

    for ruta in RIESGO:
        r = _leer(publico, ruta)
        if r is None:
            errores.append(f"falta {ruta}")
            continue
        items = r.get("items", [])
        if len(items) != N_COMUNAS:
            errores.append(f"{ruta}: {len(items)} comunas (se esperaban {N_COMUNAS})")
        if any(not (0 <= float(i.get("prob_foco", -1)) <= 1) for i in items):
            errores.append(f"{ruta}: hay probabilidades fuera de 0-1")
        if ruta == RIESGO[0] and r.get("valido_para"):
            valido = date.fromisoformat(r["valido_para"])
            if (hoy - valido).days > DIAS_MAX_ATRASO:
                errores.append(f"el riesgo es para el {valido} y hoy es {hoy}: los datos no se actualizaron")
            if (valido - hoy).days > 1:
                errores.append(f"el riesgo es para el {valido}, más de un día después de hoy ({hoy})")

    c = _leer(publico, "comunas.json")
    if c is None:
        errores.append("falta comunas.json")
    elif len(c.get("comunas", [])) != N_COMUNAS:
        errores.append(f"comunas.json: {len(c.get('comunas', []))} comunas (se esperaban {N_COMUNAS})")

    g = _leer(publico, "regiones.geojson")
    if g is None or len(g.get("features", [])) != N_COMUNAS:
        errores.append("regiones.geojson falta o no tiene las 345 comunas")

    for ruta in ("avance/activos.json", "alertas/05.json", "recomendaciones.json", "index.html"):
        if not (publico / ruta).exists():
            errores.append(f"falta {ruta}")

    clima = (m.get("datos") or {}).get("clima_hasta")
    if clima and (hoy - datetime.fromisoformat(clima).date()).days > DIAS_AVISO_CLIMA:
        avisos.append(f"el clima de NASA POWER llega solo hasta el {clima}")

    if llave:
        for p in publico.rglob("*"):
            if p.is_file() and p.suffix in {".json", ".geojson", ".csv", ".html", ".txt", ".md"}:
                if llave in p.read_text(encoding="utf-8", errors="ignore"):
                    errores.append(f"la MAP_KEY aparece en {p.relative_to(publico).as_posix()}")
    return errores, avisos
