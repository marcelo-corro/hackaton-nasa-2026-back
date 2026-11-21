# Fuentes persistentes que FIRMS no marca

Generado por `scripts/04b_fuentes_persistentes.py` el 2026-11-21. Máscara: `ref/fuentes_persistentes.csv`.

## Por qué
FIRMS marca algunas fuentes fijas (`tipo` 2) y volcanes (`tipo` 1), pero no todas, y los focos casi en tiempo real no
traen esa marca. Refinerías, fundiciones, faenas mineras, rellenos sanitarios y volcanes se detectan año tras año en el
mismo lugar y se contaban como incendios: subían la serie, el riesgo y lo «normal» de comunas como Concón, Copiapó o
Calama. La regla de los sectores de Valparaíso (`firecal.sectores.historial`) ya las detectaba de noche; en el desierto
del norte las fuentes son diurnas y esa regla no las veía.

## Regla
Celdas de 1 km (UTM 19S) y otra grilla corrida 500 m, con focos SNPP de vegetación y confianza nominal o alta
entre 2012-02-01 y 2026-01-01 (exclusivo):

- **Fuego repetido:** focos en >= 10 días de >= 5 años distintos.
- **Fuente persistente:** fuego repetido y además
  - **sin vegetación:** < 10% de vegetación en ESA WorldCover 2021 (ventana de 1,5 km), o
  - **nocturna y fija:** >= 60% de las detecciones de noche y nunca parte de un incendio de más de
    10 focos o que pase de 2 km.

Cada foco (de cualquier sensor, también los casi en tiempo real) que cae en una celda de la máscara queda marcado como
`fuente_persistente` en `firecal.calidad` y sale de `uso_base`: no se cuenta en la serie armonizada, el calendario, el
modelo de riesgo, los incendios activos ni lo «normal» de cada comuna.

## Celdas por zona (las dos grillas)
| Zona | Fuego repetido | Sin vegetación | Nocturna y fija | Persistentes |
|---|---|---|---|---|
| Austral (11, 12) | 19 | 0 | 14 | 14 |
| Centro (5, 13, 6, 7) | 417 | 4 | 88 | 88 |
| Coquimbo (4) | 22 | 0 | 2 | 2 |
| Norte (15, 1, 2, 3) | 343 | 328 | 70 | 328 |
| Sur (16, 8, 9, 14, 10) | 1 685 | 11 | 32 | 38 |

Celdas sin dato de WorldCover: 0 (no se marcan por la vía de la vegetación).

## Efecto (SNPP, 2012-02-01 a 2026-01-01)
- Detecciones marcadas: **9 802 de 305 353 (3.2%)**.
- Días-comuna con focos que se quitan: **5.8%**; comunas con alguna celda: 67;
  con más de 25 % de sus días: 36.
- Detecciones de vegetación con confianza de todos los sensores y años (MODIS 2000-, VIIRS 2012-) que salen de
  `uso_base`: 19 475 de 642 612 (3.0%).

### Comunas donde más cambia
| Código | Comuna | Días con focos | Sin fuentes persistentes | Días que se quitan (%) |
|---|---|---|---|---|
| 08112 | Hualpén | 186 | 3 | 98.4 |
| 05103 | Concón | 164 | 9 | 94.5 |
| 12101 | Punta Arenas | 164 | 11 | 93.3 |
| 05107 | Quintero | 127 | 24 | 81.1 |
| 05105 | Puchuncaví | 135 | 31 | 77.0 |
| 03304 | Huasco | 86 | 22 | 74.4 |
| 09115 | Pucón | 162 | 45 | 72.2 |
| 13125 | Quilicura | 141 | 46 | 67.4 |
| 13126 | Quinta Normal | 11 | 4 | 63.6 |
| 13116 | Lo Espejo | 16 | 6 | 62.5 |
| 02104 | Taltal | 310 | 132 | 57.4 |
| 05502 | Calera | 84 | 36 | 57.1 |
| 01107 | Alto Hospicio | 208 | 90 | 56.7 |
| 05702 | Catemu | 157 | 71 | 54.8 |
| 03101 | Copiapó | 517 | 234 | 54.7 |
| 13102 | Cerrillos | 26 | 12 | 53.8 |
| 10401 | Chaitén | 95 | 46 | 51.6 |
| 02203 | San Pedro de Atacama | 258 | 133 | 48.4 |
| 02201 | Calama | 505 | 274 | 45.7 |
| 03202 | Diego de Almagro | 295 | 165 | 44.1 |
| 02101 | Antofagasta | 516 | 300 | 41.9 |
| 03201 | Chañaral | 170 | 103 | 39.4 |
| 08110 | Talcahuano | 87 | 53 | 39.1 |
| 08306 | Nacimiento | 484 | 316 | 34.7 |
| 13128 | Renca | 38 | 25 | 34.2 |
| 03301 | Vallenar | 196 | 135 | 31.1 |
| 03103 | Tierra Amarilla | 363 | 254 | 30.0 |
| 06108 | Machalí | 108 | 76 | 29.6 |
| 12302 | Primavera | 445 | 321 | 27.9 |
| 06111 | Olivar | 29 | 21 | 27.6 |

### Comunas de referencia (incendios forestales o quemas agrícolas frecuentes; no deberían cambiar)
| Código | Comuna | Días con focos | Sin fuentes persistentes | Días que se quitan (%) |
|---|---|---|---|---|
| 09202 | Collipulli | 1 076 | 1 072 | 0.4 |
| 08301 | Los Angeles | 963 | 963 | 0.0 |
| 07401 | Linares | 598 | 598 | 0.0 |
| 07301 | Curicó | 421 | 421 | 0.0 |
| 04301 | Ovalle | 415 | 415 | 0.0 |
| 09101 | Temuco | 303 | 303 | 0.0 |
| 15201 | Putre | 168 | 168 | 0.0 |
| 15202 | General Lagos | 60 | 60 | 0.0 |

## Celdas con más días (grilla sin desfase)
| Comuna | lat | lon | Días | Años | % noche | % vegetación | Motivo |
|---|---|---|---|---|---|---|---|
| Pucón | -39.420 | -71.942 | 172 | 13 | 95.000 | 0.000 | sin_vegetacion |
| Punta Arenas | -52.943 | -70.806 | 138 | 13 | 74.000 | 68.000 | nocturna_fija |
| San Pedro de Atacama | -23.362 | -67.734 | 129 | 8 | 100.000 | 0.000 | sin_vegetacion+nocturna_fija |
| Concón | -32.929 | -71.506 | 128 | 14 | 90.000 | 34.000 | nocturna_fija |
| Nacimiento | -37.514 | -72.655 | 119 | 14 | 100.000 | 40.000 | nocturna_fija |
| Hualpén | -36.783 | -73.127 | 114 | 13 | 89.000 | 57.000 | nocturna_fija |
| Quintero | -32.787 | -71.486 | 85 | 11 | 95.000 | 67.000 | nocturna_fija |
| Primavera | -52.880 | -68.861 | 85 | 13 | 69.000 | 86.000 | nocturna_fija |
| Taltal | -25.515 | -70.161 | 76 | 10 | 0.000 | 0.000 | sin_vegetacion |
| Taltal | -25.506 | -70.170 | 74 | 10 | 0.000 | 0.000 | sin_vegetacion |
| Lago Ranco | -40.524 | -72.149 | 72 | 5 | 79.000 | 0.000 | sin_vegetacion |
| Taltal | -25.507 | -70.161 | 71 | 10 | 0.000 | 0.000 | sin_vegetacion |
| Hualpén | -36.778 | -73.120 | 65 | 12 | 100.000 | 35.000 | nocturna_fija |
| Copiapó | -27.421 | -70.259 | 64 | 13 | 89.000 | 8.000 | sin_vegetacion+nocturna_fija |
| Huasco | -28.482 | -71.249 | 60 | 14 | 100.000 | 3.000 | sin_vegetacion+nocturna_fija |
| Copiapó | -27.006 | -69.871 | 58 | 10 | 0.000 | 0.000 | sin_vegetacion |
| Arauco | -37.208 | -73.227 | 58 | 12 | 100.000 | 49.000 | nocturna_fija |
| Copiapó | -27.007 | -69.862 | 53 | 10 | 0.000 | 0.000 | sin_vegetacion |
| Diego de Almagro | -26.431 | -69.483 | 51 | 14 | 98.000 | 1.000 | sin_vegetacion+nocturna_fija |
| Taltal | -25.533 | -70.179 | 50 | 10 | 0.000 | 0.000 | sin_vegetacion |
| Tierra Amarilla | -27.569 | -69.277 | 47 | 5 | 95.000 | 0.000 | sin_vegetacion+nocturna_fija |
| Calama | -22.313 | -68.878 | 47 | 10 | 88.000 | 0.000 | sin_vegetacion+nocturna_fija |
| Chañaral | -26.306 | -70.217 | 44 | 11 | 0.000 | 2.000 | sin_vegetacion |
| Copiapó | -27.256 | -70.105 | 43 | 12 | 0.000 | 0.000 | sin_vegetacion |
| Alto Hospicio | -20.204 | -70.047 | 43 | 8 | 88.000 | 0.000 | sin_vegetacion+nocturna_fija |
| Calama | -22.486 | -68.886 | 43 | 14 | 77.000 | 0.000 | sin_vegetacion+nocturna_fija |
| Copiapó | -27.358 | -70.222 | 42 | 11 | 100.000 | 1.000 | sin_vegetacion+nocturna_fija |
| Quilicura | -33.351 | -70.796 | 41 | 12 | 91.000 | 57.000 | nocturna_fija |
| Copiapó | -27.121 | -70.177 | 40 | 12 | 0.000 | 0.000 | sin_vegetacion |
| Alto Biobío | -37.854 | -71.161 | 39 | 11 | 96.000 | 0.000 | sin_vegetacion+nocturna_fija |
| Antofagasta | -23.780 | -70.316 | 39 | 12 | 100.000 | 1.000 | sin_vegetacion+nocturna_fija |
| Catemu | -32.798 | -70.952 | 39 | 13 | 76.000 | 84.000 | nocturna_fija |
| Copiapó | -27.251 | -70.116 | 38 | 11 | 0.000 | 0.000 | sin_vegetacion |
| Alto Biobío | -37.857 | -71.162 | 38 | 8 | 92.000 | 0.000 | sin_vegetacion+nocturna_fija |
| Copiapó | -27.114 | -70.176 | 37 | 12 | 0.000 | 0.000 | sin_vegetacion |
| Quillota | -32.936 | -71.316 | 35 | 10 | 100.000 | 79.000 | nocturna_fija |
| Taltal | -25.534 | -70.170 | 35 | 10 | 0.000 | 0.000 | sin_vegetacion |
| Taltal | -25.116 | -70.305 | 35 | 11 | 0.000 | 0.000 | sin_vegetacion |
| Teno | -34.866 | -71.141 | 35 | 12 | 97.000 | 79.000 | nocturna_fija |
| Vallenar | -29.144 | -70.865 | 34 | 10 | 2.000 | 9.000 | sin_vegetacion |

## Límites
- La máscara es fija: una fuente nueva no se marca hasta repetir este paso (conviene una vez al año).
- WorldCover es de 2021. Un lugar que se quemó y quedó sin vegetación no cuenta como «sin vegetación» por un incendio
  aislado: la celda además tiene que repetirse en >= 5 años.
- Un incendio real dentro de una celda de la máscara no se cuenta (son celdas de 1 km sin vegetación o con una fuente
  industrial; el efecto en las comunas de referencia está arriba).

Fuente de cobertura: Zanaga, D. et al. (2022). *ESA WorldCover 10 m 2021 v200*. https://doi.org/10.5281/zenodo.7254221
(CC BY 4.0), leída por rango desde `https://esa-worldcover.s3.eu-central-1.amazonaws.com`.
