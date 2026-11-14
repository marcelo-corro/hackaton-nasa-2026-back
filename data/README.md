# data/

Esta carpeta **no se sube al repo**. Cada integrante la llena en su máquina.

| Carpeta | Contenido | De dónde sale |
|---|---|---|
| `raw/` | Datos tal como vienen de la fuente | FIRMS (o apuntar `FIRMS_RAW_DIR` al Drive del equipo), comunas BCN/IDE, clima |
| `interim/` | Tablas limpias y unidas | `scripts/01_ingestar_firms.py` → `focos.parquet` |
| `processed/` | Series armonizadas y features del modelo | pasos siguientes del pipeline |

Los procesados livianos que convenga compartir se suben al Drive del equipo o como Release de GitHub, no al repo.
