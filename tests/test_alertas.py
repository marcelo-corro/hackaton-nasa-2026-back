import numpy as np
import pandas as pd

from firecal.export.sectores import meta_lista
from firecal.sectores.alertas import armar_lista, lista_v04, motivos_comuna, tipo_comuna


def _sectores():
    # comuna A (3 sectores en fila), B (2), C (1)
    s = pd.DataFrame({"sector_id": ["A1", "A2", "A3", "B1", "B2", "C1"],
                      "region_id": ["A", "A", "A", "B", "B", "C"],
                      "frac_wui": [0.0, 0.9, 0.1, 0.5, 0.0, 0.0]})
    xy = np.array([[0.0, 0], [1000, 0], [2000, 0], [10000, 0], [11000, 0], [20000, 0]])
    hist = np.array([5, 1, 0, 0, 3, 9])
    return s, xy, hist


def test_tipo_comuna() -> None:
    assert tipo_comuna("bajo", True) == "fuego_activo"  # el fuego observado manda, aunque el modelo diga bajo
    assert tipo_comuna("muy_alto", False) == "alerta"
    assert tipo_comuna("medio", False) == "vigilancia"
    assert tipo_comuna("bajo", False) is None


def test_lista_fuego_activo_primero_y_por_cercania() -> None:
    s, xy, hist = _sectores()
    riesgo = pd.DataFrame({"region_id": ["A", "B", "C"], "prob_foco": [0.05, 0.40, 0.01],
                           "nivel": ["medio", "muy_alto", "bajo"]})
    foco_reciente = np.array([[2100.0, 0]])  # junto a A3
    t = armar_lista(s, xy, riesgo, hist, foco_reciente, {"A"})
    assert list(t["tipo"].drop_duplicates()) == ["fuego_activo", "alerta"]  # C (bajo, sin fuego) no entra
    assert list(t[t["region_id"] == "A"]["sector_id"]) == ["A3", "A2", "A1"]  # por cercanía al foco
    assert list(t[t["region_id"] == "B"]["sector_id"]) == ["B2", "B1"]  # historial y luego interfaz
    assert t["orden"].tolist() == list(range(1, len(t) + 1))
    assert (t[t["tipo"] == "fuego_activo"]["motivo_orden"] == "cerca_fuego_reciente").all()


def test_lista_vacia_si_todo_es_bajo_y_sin_fuego() -> None:
    s, xy, hist = _sectores()
    riesgo = pd.DataFrame({"region_id": ["A", "B", "C"], "prob_foco": 0.01, "nivel": "bajo"})
    t = armar_lista(s, xy, riesgo, hist, np.empty((0, 2)), set())
    assert t.empty
    m = meta_lista(24, t)
    assert m["vacia"] and m["mensaje"] and m["tipo_lista"] == "alertas"
    assert meta_lista(168, t)["tipo_lista"] == "prioridades_semana"


def test_lista_v04_siempre_llena() -> None:
    s, xy, hist = _sectores()
    riesgo = pd.DataFrame({"region_id": ["A", "B", "C"], "prob_foco": 0.01, "nivel": "bajo"})
    assert len(lista_v04(s, riesgo, hist, n=5)) == 5  # la regla anterior rellenaba aunque el riesgo fuera bajo


def test_motivos_comuna() -> None:
    dias = pd.Series(pd.to_datetime(["2024-01-10", "2025-01-05", "2025-12-30", "2025-12-31"]))
    m = motivos_comuna(dias, pd.Timestamp("2025-12-31"), 1, ["calor"], {"calor": "Temperatura máxima sobre 30 °C"},
                       pd.Timestamp("2024-01-01"))
    assert m["fuego_activo"] and m["dias_con_fuego_7d"] == 2 and m["ultimo_fuego"] == "2025-12-31"
    assert m["pct_dias_con_fuego_mes"] == round(100 * 2 / 62, 1)  # 2 días con fuego en 62 días de enero
    assert any("°C" in x for x in m["motivos"])  # no se pasa a minúscula la unidad
    assert motivos_comuna(pd.Series([], dtype="datetime64[ns]"), pd.Timestamp("2025-12-31"), 1, [], {},
                          pd.Timestamp("2024-01-01"))["fuego_activo"] is False
