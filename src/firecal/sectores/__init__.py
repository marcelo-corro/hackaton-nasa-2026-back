"""Sectores dentro de la comuna (piloto A+, Región de Valparaíso).

Qué hay en cada sector (celda de 1 km recortada a la comuna) y qué NO se afirma:
- historial de focos (FIRMS VIIRS Suomi NPP, 2012-2025): DESCRIPTIVO, dónde ha habido fuego;
- capas fijas del territorio (vegetación ESA WorldCover, interfaz con viviendas WUI, pendiente Copernicus DEM):
  DESCRIPTIVAS, qué hay en el sector;
- el riesgo con probabilidad es el de la COMUNA (modelo validado de firecal.model); el sector no tiene probabilidad
  propia (medido: en Valparaíso el historial de una celda no anticipa dónde cae el fuego mejor que el azar).
"""
