"""Genera archivos de ejemplo del contrato (contracts/ejemplos/) con NÚMEROS INVENTADOS.

Sirven para que el front se desarrolle antes de que existan datos reales. Todos llevan "ejemplo": true.
Los contornos de las comunas son rectángulos aproximados, no límites oficiales.

Uso:
    python scripts/00_generar_ejemplos_contrato.py
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "contracts" / "ejemplos"
CONTRATO = "0.1"
GENERADO = "2026-11-14T00:00:00Z"

REGIONES = [
    # region_id, nombre, región, rectángulo aproximado (lon_min, lat_min, lon_max, lat_max)
    ("05101", "Valparaíso", "Valparaíso", (-71.75, -33.20, -71.55, -33.00)),
    ("05109", "Viña del Mar", "Valparaíso", (-71.58, -33.08, -71.45, -32.95)),
]

# Más focos en verano (dic-mar), como en Chile central. Solo para que el ejemplo se vea realista.
ESTACIONALIDAD = np.array([1.0, 1.2, 0.9, 0.5, 0.2, 0.1, 0.05, 0.1, 0.2, 0.4, 0.6, 0.9])


def _nivel_calendario(p: float) -> str:
    if p < 25:
        return "baja"
    if p < 75:
        return "normal"
    if p < 95:
        return "alta"
    return "extrema"


def _escribir_json(ruta: Path, datos: dict) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def calendario(region_id: str, nombre: str, rng: np.random.Generator) -> dict:
    anios = range(2000, 2026)
    base = rng.gamma(shape=2.0, scale=4.0, size=(len(anios), 12)) * ESTACIONALIDAD
    base[[2017 - 2000, 2023 - 2000], :] *= 3  # años "extremos" de ejemplo: 2017 y 2023

    registros = []
    for i, anio in enumerate(anios):
        for m in range(12):
            if anio == 2000 and m < 10:
                continue  # MODIS parte en nov-2000
            modis = int(round(base[i, m]))
            viirs = int(round(base[i, m] * 3.4 + rng.normal(0, 1))) if anio >= 2012 else None
            viirs = max(viirs, 0) if viirs is not None else None
            armonizado = float(base[i, m])
            historia = base[:, m]
            percentil = float((historia < armonizado).mean() * 100)
            registros.append(
                {
                    "anio": anio,
                    "mes": m + 1,
                    "modis": modis,
                    "viirs": viirs,
                    "armonizado": round(armonizado, 1),
                    "armonizado_p05": round(armonizado * 0.85, 1),
                    "armonizado_p95": round(armonizado * 1.15, 1),
                    "percentil": round(percentil),
                    "nivel": _nivel_calendario(percentil),
                }
            )
    return {
        "contrato": CONTRATO,
        "ejemplo": True,
        "region_id": region_id,
        "nombre": nombre,
        "unidad": "focos de vegetación (tipo 0) por mes",
        "unidad_armonizada": "equivalente MODIS",
        "metodo_armonizacion": "ejemplo (números inventados)",
        "registros": registros,
    }


def main() -> None:
    rng = np.random.default_rng(2026)

    _escribir_json(
        SALIDA / "manifest.json",
        {
            "contrato": CONTRATO,
            "ejemplo": True,
            "generado_utc": GENERADO,
            "periodo": {"desde": "2000-11", "hasta": "2025-12"},
            "regiones": [r[0] for r in REGIONES],
            "archivos": {
                "regiones": "regiones.geojson",
                "calendario": "calendario/{region_id}.json",
                "riesgo": "riesgo/ultimo.json",
                "focos": "focos/{region_id}.csv",
                "metricas": "metricas.json",
            },
        },
    )

    features = []
    for region_id, nombre, region, (x0, y0, x1, y1) in REGIONES:
        features.append(
            {
                "type": "Feature",
                "properties": {"region_id": region_id, "nombre": nombre, "region": region, "pais": "CL"},
                "geometry": {"type": "Polygon", "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]},
            }
        )
    _escribir_json(SALIDA / "regiones.geojson", {"type": "FeatureCollection", "features": features})

    for region_id, nombre, _, _ in REGIONES:
        _escribir_json(SALIDA / "calendario" / f"{region_id}.json", calendario(region_id, nombre, rng))

    _escribir_json(
        SALIDA / "riesgo" / "ultimo.json",
        {
            "contrato": CONTRATO,
            "ejemplo": True,
            "calculado_utc": GENERADO,
            "valido_para": "2026-11-15",
            "horizonte_horas": 24,
            "modelo": "ejemplo (números inventados)",
            "items": [
                {"region_id": "05101", "prob_foco": 0.08, "percentil": 61, "nivel": "medio"},
                {"region_id": "05109", "prob_foco": 0.21, "percentil": 88, "nivel": "alto"},
            ],
        },
    )

    for region_id, _, _, (x0, y0, x1, y1) in REGIONES:
        ruta = SALIDA / "focos" / f"{region_id}.csv"
        ruta.parent.mkdir(parents=True, exist_ok=True)
        with ruta.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["fecha", "hora_utc", "lat", "lon", "sensor", "satelite", "confianza", "frp", "tipo"])
            for fecha, hora, sensor, sat, conf in [
                ("2024-02-02", "0315", "MODIS", "Terra", "alta"),
                ("2024-02-02", "0600", "VIIRS", "SNPP", "nominal"),
                ("2024-02-03", "1830", "VIIRS", "SNPP", "alta"),
            ]:
                lat = round(rng.uniform(y0, y1), 4)
                lon = round(rng.uniform(x0, x1), 4)
                w.writerow([fecha, hora, lat, lon, sensor, sat, conf, round(rng.uniform(2, 60), 1), 0])

    _escribir_json(
        SALIDA / "metricas.json",
        {
            "contrato": CONTRATO,
            "ejemplo": True,
            "modelo": None,
            "periodo_prueba": None,
            "auc": None,
            "precision_media": None,
            "captura_top10": None,
            "nota": "Pendiente: todavía no hay modelo validado.",
        },
    )
    print(f"Ejemplos escritos en {SALIDA}")


if __name__ == "__main__":
    main()
