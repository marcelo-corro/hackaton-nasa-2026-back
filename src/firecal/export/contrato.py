"""Exportación al contrato del front v0.2 (tarea B3). Forma exacta en contracts/README.md.

Los constructores (`manifest`, `calendario_region`, `riesgo_ultimo`, ...) son funciones puras que devuelven
diccionarios o textos; `exportar` los escribe a disco.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import mapping

VERSION_CONTRATO = "0.2"
TOLERANCIA_SIMPLIFICACION = 0.005  # grados (~500 m)
DECIMALES_COORDENADAS = 4
LIMITE_GEOJSON_MB = 3.0

COLUMNAS_FOCOS_CSV = ["fecha", "hora_utc", "lat", "lon", "sensor", "satelite", "confianza", "frp", "tipo"]
NOTA_METRICAS_PENDIENTE = "Pendiente: todavía no hay modelo validado."
ARCHIVOS = {
    "regiones": "regiones.geojson",
    "calendario": "calendario/{region_id}.json",
    "riesgo": "riesgo/ultimo.json",
    "focos": "focos/{region_id}.csv",
    "metricas": "metricas.json",
}


def _escribir_json(ruta: Path, datos: dict, indent: int | None = None) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    separadores = None if indent else (",", ":")
    texto = json.dumps(datos, ensure_ascii=False, indent=indent, separators=separadores) + "\n"
    with open(ruta, "w", encoding="utf-8", newline="") as f:  # newline="" evita que Windows meta \r\n
        f.write(texto)


def _numero(valor: object, decimales: int = 1) -> float | None:
    """Número JSON con `decimales`; los nulos (NaN, NA, None) pasan a None."""
    if valor is None or valor is pd.NA or pd.isna(valor):
        return None
    return round(float(valor), decimales)


def _entero(valor: object) -> int | None:
    if valor is None or valor is pd.NA or pd.isna(valor):
        return None
    return int(valor)


def _ahora_utc(ahora: datetime | None) -> str:
    return (ahora or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- manifest -----------------------------------------------------------------------------------------


def manifest(calendario: pd.DataFrame, ahora: datetime | None = None) -> dict:
    ordenado = calendario.sort_values(["anio", "mes"])
    primero, ultimo = ordenado.iloc[0], ordenado.iloc[-1]
    return {
        "contrato": VERSION_CONTRATO,
        "ejemplo": False,
        "generado_utc": _ahora_utc(ahora),
        "periodo": {
            "desde": f"{int(primero['anio']):04d}-{int(primero['mes']):02d}",
            "hasta": f"{int(ultimo['anio']):04d}-{int(ultimo['mes']):02d}",
        },
        "regiones": sorted(calendario["region_id"].astype(str).unique()),
        "archivos": dict(ARCHIVOS),
    }


# --- regiones.geojson ---------------------------------------------------------------------------------


def _redondear(geom: shapely.Geometry) -> shapely.Geometry:
    return shapely.transform(geom, lambda xy: np.round(xy, DECIMALES_COORDENADAS))


def regiones_geojson(comunas: gpd.GeoDataFrame) -> dict:
    """GeoJSON simplificado para la web (tolerancia ~0,005°, 4 decimales). Una comuna por Feature."""
    if comunas.crs is not None and comunas.crs.to_epsg() != 4326:
        comunas = comunas.to_crs(4326)
    features = []
    for fila in comunas.sort_values("region_id").itertuples():
        geom = shapely.make_valid(fila.geometry.simplify(TOLERANCIA_SIMPLIFICACION, preserve_topology=True))
        geom = _redondear(geom)
        if geom.is_empty:  # una comuna diminuta puede desaparecer al simplificar: conservar el original
            geom = _redondear(fila.geometry)
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "region_id": str(fila.region_id),
                    "nombre": str(fila.nombre),
                    "region": str(fila.region),
                    "pais": "CL",
                },
                "geometry": mapping(geom),
            }
        )
    return {"type": "FeatureCollection", "features": features}


# --- calendario/{region_id}.json ----------------------------------------------------------------------


def calendario_region(registros: pd.DataFrame, nombre: str) -> dict:
    """`registros`: filas del calendario de una sola comuna."""
    registros = registros.sort_values(["anio", "mes"])
    return {
        "contrato": VERSION_CONTRATO,
        "ejemplo": False,
        "region_id": str(registros["region_id"].iloc[0]),
        "nombre": nombre,
        "unidad": "focos de vegetación (tipo 0) por mes",
        "unidad_armonizada": "equivalente MODIS",
        "metodo_armonizacion": str(registros["metodo"].iloc[0]),
        "registros": [
            {
                "anio": int(r.anio),
                "mes": int(r.mes),
                "modis": _entero(r.modis),
                "viirs": _entero(r.viirs),
                "armonizado": _numero(r.armonizado),
                "armonizado_p05": _numero(r.armonizado_p05),
                "armonizado_p95": _numero(r.armonizado_p95),
                "mediana_historica": _numero(r.mediana_historica),
                "percentil": _numero(r.percentil),
                "nivel": str(r.nivel),
            }
            for r in registros.itertuples()
        ],
    }


# --- focos/{region_id}.csv ----------------------------------------------------------------------------


def focos_csv(focos_region: pd.DataFrame) -> str:
    """CSV de los focos de vegetación de una comuna (todas las confianzas). Sin focos: solo el encabezado."""
    salida = focos_region.loc[focos_region["es_vegetacion"], COLUMNAS_FOCOS_CSV].copy()
    salida["fecha"] = pd.to_datetime(salida["fecha"]).dt.strftime("%Y-%m-%d")
    salida = salida.sort_values(["fecha", "hora_utc", "satelite"])
    salida["lat"] = salida["lat"].round(4)
    salida["lon"] = salida["lon"].round(4)
    salida["frp"] = salida["frp"].round(1)
    return salida.to_csv(index=False, lineterminator="\n", na_rep="")


# --- riesgo/ultimo.json y metricas.json ---------------------------------------------------------------


def riesgo_ultimo(riesgo: pd.DataFrame | None, ahora: datetime | None = None) -> dict:
    """Riesgo del `valido_para` más reciente; sin riesgo de A, `items` vacío."""
    base = {"contrato": VERSION_CONTRATO, "ejemplo": False}
    if riesgo is None or riesgo.empty:
        return {**base, "calculado_utc": None, "valido_para": None, "horizonte_horas": None, "modelo": None, "items": []}
    ultimo = riesgo[riesgo["valido_para"] == riesgo["valido_para"].max()]
    horizonte = int(ultimo["horizonte_horas"].min())
    ultimo = ultimo[ultimo["horizonte_horas"] == horizonte].sort_values("region_id")
    return {
        **base,
        "calculado_utc": _ahora_utc(ahora),
        "valido_para": pd.Timestamp(ultimo["valido_para"].iloc[0]).strftime("%Y-%m-%d"),
        "horizonte_horas": horizonte,
        "modelo": str(ultimo["modelo"].iloc[0]),
        "items": [
            {
                "region_id": str(r.region_id),
                "prob_foco": round(float(r.prob_foco), 3),
                "percentil": _numero(r.percentil),
                "nivel": str(r.nivel),
            }
            for r in ultimo.itertuples()
        ],
    }


def metricas(datos: dict | None) -> dict:
    base = {"contrato": VERSION_CONTRATO, "ejemplo": False}
    claves = ["modelo", "periodo_prueba", "auc", "precision_media", "captura_top10", "nota"]
    if not datos:
        return {**base, **dict.fromkeys(claves), "nota": NOTA_METRICAS_PENDIENTE}
    return {**base, **{k: datos.get(k) for k in claves}}


# --- orquestador --------------------------------------------------------------------------------------


def exportar(
    calendario: pd.DataFrame,
    comunas: gpd.GeoDataFrame,
    focos: pd.DataFrame,
    destino: Path,
    riesgo: pd.DataFrame | None = None,
    datos_metricas: dict | None = None,
    ahora: datetime | None = None,
) -> dict:
    """Escribe todos los archivos del contrato en `destino` (se vacía antes). Devuelve un resumen."""
    destino = Path(destino)
    if destino.exists():
        shutil.rmtree(destino)
    destino.mkdir(parents=True)

    nombres = comunas.set_index(comunas["region_id"].astype(str))["nombre"].to_dict()
    ids = sorted(calendario["region_id"].astype(str).unique())

    _escribir_json(destino / ARCHIVOS["regiones"], regiones_geojson(comunas))
    _escribir_json(destino / "manifest.json", manifest(calendario, ahora), indent=2)

    for region_id, registros in calendario.groupby(calendario["region_id"].astype(str)):
        _escribir_json(destino / "calendario" / f"{region_id}.json", calendario_region(registros, nombres[region_id]))

    con_comuna = focos[focos["region_id"].notna()]
    por_region = {str(k): v for k, v in con_comuna.groupby("region_id")}
    (destino / "focos").mkdir()
    for region_id in ids:
        with open(destino / "focos" / f"{region_id}.csv", "w", encoding="utf-8", newline="") as f:
            f.write(focos_csv(por_region.get(region_id, con_comuna.iloc[0:0])))

    _escribir_json(destino / ARCHIVOS["riesgo"], riesgo_ultimo(riesgo, ahora), indent=2)
    _escribir_json(destino / ARCHIVOS["metricas"], metricas(datos_metricas), indent=2)

    archivos = [p for p in destino.rglob("*") if p.is_file()]
    return {
        "archivos": len(archivos),
        "tamano_mb": sum(p.stat().st_size for p in archivos) / 1e6,
        "geojson_mb": (destino / ARCHIVOS["regiones"]).stat().st_size / 1e6,
        "comunas": len(ids),
    }
