"""Agrupación de focos en incendios (paso 6, `scripts/06_eventos.py`). Resultados en docs/eventos.md.

Hipótesis original: VIIRS (375 m) parte un mismo incendio en más píxeles que MODIS (1 km), así que contando
eventos en vez de focos la diferencia entre sensores debería acercarse a 1.

Resultado (14-11-2026): se cumple solo en parte. Con eventos de 2 km y 2 días la razón Suomi NPP / MODIS baja
de ~3,2 a ~2,3 (2012-2016), pero no a 1: VIIRS además detecta incendios chicos que MODIS no ve. La
coincidencia entre sensores (`evento_detectado_por`) mide directamente esa sensibilidad y la deriva de MODIS.

Módulo: `agrupar` (etiquetar eventos, resumirlos y medir coincidencia entre sensores).
"""
