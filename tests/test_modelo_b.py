import numpy as np
import pandas as pd

from firecal.export.sectores import campos_modelo_b
from firecal.sectores.modelo_b import (
    ESTATICAS, Historial, captura_top, codigo_celda, dia_entero, etiqueta_grande, tabla_condicional,
)


def test_historial_cuenta_ventanas_y_dias_desde_ultimo() -> None:
    c = codigo_celda([0, 0, 0, 1], [0, 0, 0, 0])
    h = Historial(c, np.array([10, 12, 12, 11]))  # el 12 repetido cuenta una vez
    celda0 = codigo_celda([0], [0])
    assert h.contar(celda0, np.array([0]), np.array([12]))[0] == 1  # antes del día 12: solo el 10
    assert h.contar(celda0, np.array([0]), np.array([13]))[0] == 2
    assert h.contar(celda0, np.array([9]), np.array([12]))[0] == 1  # ventana [9, 12)
    assert h.dias_desde_ultimo(celda0, np.array([15]))[0] == 3
    assert h.dias_desde_ultimo(codigo_celda([5], [5]), np.array([15]))[0] == 9999  # nunca ardió


def _escenario():
    # comuna A con 3 sectores en fila (ix 0, 1, 2); comuna B lejos con 1 sector
    s = pd.DataFrame({"sector_id": ["A_0", "A_1", "A_2", "B_9"], "region_id": ["A", "A", "A", "B"],
                      "ix": [0, 1, 2, 9], "iy": [0, 0, 0, 9]})
    for c in ESTATICAS:
        s[c] = 0.0
    xy_s = np.array([[500.0, 500], [1500, 500], [2500, 500], [9500, 9500]])
    f = pd.DataFrame({"sector_id": ["A_0", "A_0", "A_1"], "region_id": ["A", "A", "A"],
                      "fecha_local": pd.to_datetime(["2015-01-01", "2015-01-05", "2015-01-06"])})
    xy_f = np.array([[500.0, 500], [500, 500], [1500, 500]])
    return s, f, xy_f, xy_s


def test_tabla_condicional_sin_fuga() -> None:
    s, f, xy_f, xy_s = _escenario()
    t = tabla_condicional(s, f, xy_f, xy_s)
    d6 = t[t["fecha"] == pd.Timestamp("2015-01-06")].set_index("sector_id")
    assert set(t["region_id"]) == {"A"}  # solo días con fuego en la comuna
    assert d6.loc["A_1", "y"] == 1.0 and d6.loc["A_0", "y"] == 0.0
    assert d6.loc["A_1", "hist_dias"] == 0  # su propio fuego del día 6 no entra en sus variables
    assert d6.loc["A_0", "hist_dias"] == 2
    assert d6.loc["A_1", "hist_dias_vecinos"] == 2  # A_0 es vecino
    assert d6.loc["A_1", "recientes_vecinos"] == 1  # fuego del 05 en A_0 (ventana 03-05)
    assert d6.loc["A_1", "dist_foco_reciente_km"] == 1.0
    assert d6.loc["A_1", "comuna_con_fuego_reciente"] == 1.0
    d1 = t[t["fecha"] == pd.Timestamp("2015-01-01")].set_index("sector_id")
    assert d1.loc["A_0", "comuna_con_fuego_reciente"] == 0.0 and d1.loc["A_0", "dist_foco_reciente_km"] == 30.0


def test_tabla_para_predecir_otro_dia() -> None:
    s, f, xy_f, xy_s = _escenario()
    d = int(dia_entero(pd.Series([pd.Timestamp("2015-01-07")]))[0])
    t = tabla_condicional(s, f, xy_f, xy_s, pares=[("A", d), ("B", d)])
    assert len(t) == 4 and t["y"].sum() == 0
    assert t.set_index("sector_id").loc["A_1", "hist_dias"] == 1


def test_captura_top_y_etiqueta_grande() -> None:
    t = pd.DataFrame({"region_id": ["A"] * 10, "dia": 1, "y": [1.0] + [0.0] * 9})
    assert captura_top(t, np.arange(10)[::-1].astype(float)) == 1.0  # el que ardió tiene el mayor puntaje
    assert captura_top(t, np.arange(10).astype(float)) == 0.0
    f = pd.DataFrame({"sector_id": ["A_0", "A_1"], "fecha_local": pd.to_datetime(["2015-01-01"] * 2),
                      "focos_incendio": [50, 3]})
    q = pd.DataFrame({"sector_id": ["A_0", "A_1"], "dia": dia_entero(pd.Series(pd.to_datetime(["2015-01-01"] * 2)))})
    assert etiqueta_grande(q, f).tolist() == [1.0, 0.0]


def test_campos_modelo_b() -> None:
    fila = pd.Series({"prob_condicional": 0.2, "prob_grande": 0.7, "percentil_en_comuna": 95.0})
    c = campos_modelo_b(fila, 0.10)
    assert c["prob_fuego_24h"] == 0.02 and c["prob_incendio_grande"] == 0.7
    assert campos_modelo_b(pd.Series({"x": 1}), 0.1) == {}
