"""Armonización MODIS <-> VIIRS (paso 5, `scripts/05_armonizar.py`). Resultados en docs/armonizacion.md.

Módulos:
- `conteos`: conteos mensuales por comuna y satélite (grilla completa; nulo antes de que exista el satélite).
- `calibracion`: métodos que convierten el conteo de un satélite al de otro, con intervalo de predicción.
- `evaluacion`: métricas fuera de muestra a escala comuna, región y país.
- `serie`: arma la serie mensual del contrato `serie_mensual` con la regla por período.

Decisiones (14-11-2026):
- Unidad: focos equivalentes MODIS (Terra + Aqua, órbita nominal, procesamiento previo a 2018).
- Período de calibración VIIRS -> MODIS: 2012-03 a 2017-12. Desde 2018 MODIS cambia de versión de
  procesamiento y su órbita se desvía (MODIS observado queda 8-24 % bajo lo esperado), así que desde 2018-01 la
  serie usa VIIRS Suomi NPP convertido; hasta 2017-12 usa MODIS observado; antes de Aqua (2002-07), Terra
  convertido a Terra + Aqua.
- Método: se comparan 8 métodos fuera de muestra (calibra 2012-2015, prueba 2016-2017). Gana el factor único
  (razón ~3,18): los efectos por región o temporada no son estables entre años y empeoran la predicción.
- No se suman satélites que ven los mismos incendios (Suomi NPP y NOAA-20). El factor NOAA-20 -> Suomi NPP queda
  en data/processed/calibracion.json para cuando Suomi NPP deje de entregar datos.
"""
