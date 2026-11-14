import numpy as np
import pandas as pd

from firecal.events.agrupar import etiquetar_eventos, evento_detectado_por, resumir_eventos


def _focos(filas) -> pd.DataFrame:
    df = pd.DataFrame(filas, columns=["lat", "lon", "fecha_local", "frp"])
    df["fecha_local"] = pd.to_datetime(df["fecha_local"])
    return df


def test_agrupa_por_cercania_en_espacio_y_tiempo() -> None:
    focos = _focos([
        (-33.000, -71.500, "2024-02-02", 10.0),
        (-33.010, -71.500, "2024-02-03", 5.0),   # ~1,1 km y 1 día: mismo evento
        (-33.020, -71.500, "2024-02-04", 5.0),   # encadenado con el anterior: mismo evento
        (-33.000, -71.500, "2024-02-10", 1.0),   # mismo lugar, 8 días después: otro evento
        (-33.500, -71.500, "2024-02-02", 1.0),   # ~55 km: otro evento
    ])
    et = etiquetar_eventos(focos, d_km=2.0, t_dias=2.0)

    assert et[0] == et[1] == et[2]
    assert len({et[0], et[3], et[4]}) == 3

    resumen = resumir_eventos(focos, et).set_index("evento")
    grande = resumen.loc[et[0]]
    assert grande.n_focos == 3 and grande.dias == 3 and np.isclose(grande.frp_total, 20.0)


def test_coincidencia_entre_sensores() -> None:
    viirs = _focos([
        (-33.000, -71.500, "2024-02-02", 10.0),
        (-34.000, -71.000, "2024-02-02", 1.0),
    ])
    modis = _focos([(-33.005, -71.505, "2024-02-02", 30.0)])  # solo ve el primero
    et = etiquetar_eventos(viirs)

    visto = evento_detectado_por(viirs, et, modis, d_km=2.0, t_dias=1.0)
    assert visto[et[0]] and not visto[et[1]]
