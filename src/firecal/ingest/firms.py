"""Carga los CSV anuales de FIRMS (MODIS y VIIRS) en una sola tabla con columnas comunes.

Salida (contrato interno, data/interim/focos.parquet), una fila por detección:

    fecha            datetime64   fecha de adquisición (UTC)
    hora_utc         string       HHMM
    lat, lon         float        grados decimales
    sensor           string       MODIS | VIIRS
    satelite         string       Terra | Aqua | SNPP | NOAA20 | NOAA21
    confianza        string       baja | nominal | alta (misma escala para ambos sensores)
    confianza_modis  Int16        0-100, solo MODIS (VIIRS no tiene valor numérico)
    brillo_k         float        temperatura de brillo (MODIS: brightness, VIIRS: bright_ti4)
    frp              float        potencia radiativa del fuego (MW)
    dia_noche        string       D | N
    tipo             Int8         0 vegetación, 1 volcán, 2 otra fuente fija, 3 costa afuera (NRT no lo trae)
    version          string       versión del producto FIRMS
    archivo          string       archivo de origen
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

COLUMNAS = [
    "fecha", "hora_utc", "lat", "lon", "sensor", "satelite", "confianza", "confianza_modis",
    "brillo_k", "frp", "dia_noche", "tipo", "version", "archivo",
]

_SATELITES = {
    "T": "Terra", "TERRA": "Terra", "A": "Aqua", "AQUA": "Aqua",
    "N": "SNPP", "NPP": "SNPP", "1": "NOAA20", "N20": "NOAA20", "2": "NOAA21", "N21": "NOAA21",
}
_CONFIANZA_VIIRS = {"l": "baja", "n": "nominal", "h": "alta"}


def es_csv_valido(ruta: Path) -> bool:
    """False si el archivo está vacío o no es un CSV de FIRMS.

    Ojo: las descargas fallidas de VIIRS NOAA-20 quedaron guardadas como `.csv` pero contienen
    la respuesta 404 en JSON. Esta función las deja fuera.
    """
    if ruta.stat().st_size == 0:
        return False
    with ruta.open("r", encoding="utf-8", errors="replace") as f:
        primera_linea = f.readline().strip()
    return primera_linea.startswith("latitude,")


def _confianza_modis(valor: pd.Series) -> pd.Series:
    # Umbrales que usa FIRMS para MODIS: 0-29 baja, 30-79 nominal, 80-100 alta.
    categorias = pd.cut(valor, bins=[-1, 29, 79, 100], labels=["baja", "nominal", "alta"])
    return categorias.astype("string")


def normalizar(df: pd.DataFrame, archivo: str = "") -> pd.DataFrame:
    """Lleva un CSV de FIRMS (MODIS o VIIRS) a las columnas comunes definidas en COLUMNAS."""
    if df.empty:
        return pd.DataFrame(columns=COLUMNAS)

    instrumento = str(df["instrument"].iloc[0]).strip().upper()
    if instrumento not in {"MODIS", "VIIRS"}:
        raise ValueError(f"Instrumento desconocido en {archivo or 'CSV'}: {instrumento!r}")

    salida = pd.DataFrame(
        {
            "fecha": pd.to_datetime(df["acq_date"]),
            "hora_utc": df["acq_time"].astype(str).str.zfill(4),
            "lat": df["latitude"].astype(float),
            "lon": df["longitude"].astype(float),
            "sensor": instrumento,
            "satelite": df["satellite"].astype(str).str.strip().str.upper().map(_SATELITES),
            "frp": df["frp"].astype(float),
            "dia_noche": df["daynight"].astype("string"),
            "tipo": df["type"].astype("Int8") if "type" in df else pd.Series(pd.NA, index=df.index, dtype="Int8"),
            "version": df["version"].astype("string"),
            "archivo": archivo,
        }
    )

    if instrumento == "MODIS":
        confianza = pd.to_numeric(df["confidence"], errors="coerce")
        salida["confianza_modis"] = confianza.astype("Int16")
        salida["confianza"] = _confianza_modis(confianza)
        salida["brillo_k"] = df["brightness"].astype(float)
    else:
        salida["confianza_modis"] = pd.Series(pd.NA, index=df.index, dtype="Int16")
        salida["confianza"] = df["confidence"].astype(str).str.strip().str.lower().map(_CONFIANZA_VIIRS).astype("string")
        salida["brillo_k"] = df["bright_ti4"].astype(float)

    desconocidos = salida["satelite"].isna()
    if desconocidos.any():
        valores = sorted(df.loc[desconocidos, "satellite"].astype(str).unique())
        raise ValueError(f"Satélite sin mapear en {archivo or 'CSV'}: {valores}")

    return salida[COLUMNAS]


def cargar_directorio(directorio: Path) -> tuple[pd.DataFrame, list[str]]:
    """Lee todos los CSV de FIRMS de un directorio.

    Devuelve la tabla unida y ordenada por fecha y hora, y la lista de archivos omitidos
    (vacíos o que no son CSV de FIRMS).
    """
    directorio = Path(directorio)
    if not directorio.is_dir():
        raise FileNotFoundError(f"No existe la carpeta de FIRMS: {directorio}")

    partes: list[pd.DataFrame] = []
    omitidos: list[str] = []
    for ruta in sorted(directorio.glob("*.csv")):
        if not es_csv_valido(ruta):
            omitidos.append(ruta.name)
            continue
        partes.append(normalizar(pd.read_csv(ruta), archivo=ruta.name))

    if not partes:
        return pd.DataFrame(columns=COLUMNAS), omitidos

    focos = pd.concat(partes, ignore_index=True)
    focos = focos.sort_values(["fecha", "hora_utc", "sensor"], kind="stable").reset_index(drop=True)
    return focos, omitidos
