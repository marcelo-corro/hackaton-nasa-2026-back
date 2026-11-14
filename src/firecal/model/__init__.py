"""Riesgo de focos a 24-48 h (pendiente).

Punto de partida: la prueba de Seba (Drive: informes/datos_8B/prediccion/prueba_prediccion.py),
AUC 0,75 solo con historia y 0,81 con el clima real de mañana (optimista: pronóstico perfecto).

Plan:
- Objetivo: al menos un foco VIIRS en la celda/comuna mañana.
- Features: historia armonizada, focos en celdas vecinas, clima de hoy, pronóstico real,
  NDVI, temperatura de superficie, cobertura de suelo.
- Validación temporal (entrenar <= 2021, probar 2022-2025), métricas AUC, AP, captura en el top 10 %
  y calibración de probabilidades.
- Foco en propagación (donde el modelo acierta); declarar el límite en ignición.
"""
