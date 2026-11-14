"""Agrupación de focos en incendios (pendiente).

Hipótesis a probar: VIIRS (375 m) parte un mismo incendio en más píxeles que MODIS (1 km), así que
contando eventos en vez de focos la diferencia entre sensores debería ser mucho menor.

Plan: clustering espaciotemporal (ST-DBSCAN o unión de focos a < X km y < Y días), comparar
conteo de eventos MODIS vs VIIRS en el traslape y ver si la razón se acerca a 1.
"""
