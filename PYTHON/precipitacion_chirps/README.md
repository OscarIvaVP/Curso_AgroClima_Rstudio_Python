# Precipitación Mensual por Polígono (CHIRPS v2.0) — Python

Script en Python que descarga automáticamente los datos globales de precipitación **CHIRPS v2.0**, los recorta a tus polígonos (subcuencas, fincas, municipios, etc.) y genera mapas, gráficos y un Excel con la lluvia mensual y acumulada anual.

---

## 1. ¿Qué hace este script?

A partir de un shapefile con tus áreas de interés, el script:

1. Descarga los 12 rásters mensuales de CHIRPS del año configurado (por defecto 2024) desde los servidores de la UCSB.
2. Recorta y enmascara esos rásters usando tus polígonos.
3. Aumenta la resolución (remuestreo bilineal x20) para que incluso polígonos pequeños contengan varios píxeles.
4. Calcula la **precipitación promedio mensual** y el **acumulado anual** por polígono.
5. Genera mapas de calor, gráfico de barras y un Excel con los resultados.

---

## 2. Fuente de información: CHIRPS v2.0

**CHIRPS** (*Climate Hazards Group InfraRed Precipitation with Station data*) es un dataset cuasi-global especialmente diseñado para el monitoreo de sequías y la planificación agrícola.

| Característica | Valor |
|---|---|
| Institución | Climate Hazards Center — Universidad de California, Santa Barbara (UCSB) |
| Resolución espacial | 0.05° (~5 km × 5 km en el ecuador) |
| Cobertura geográfica | Global entre 50°S y 50°N |
| Serie temporal | Desde 1981 hasta el presente |
| Frecuencia | Mensual |
| Unidades | mm/mes |
| Tipo de dato | Mezcla (*blended*) de estimaciones satelitales infrarrojas + estaciones meteorológicas terrestres |
| Servidor de descarga | `https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_monthly/tifs/` |

**Más información:** <https://www.chc.ucsb.edu/data/chirps>

---

## 3. Requisitos previos

- **Python 3.9 o superior**.
- **Conexión a internet** (el script descarga ~12 GeoTIFFs comprimidos).
- Un **shapefile** (`.shp` + `.shx` + `.dbf` + `.prj`) con los polígonos de tu área de estudio.
  - Puede estar en cualquier sistema de coordenadas; el script lo reproyecta a `EPSG:4326`.
  - Debe tener al menos una columna que identifique a cada polígono (por ejemplo: `Nombre`, `ID_CUENCA`, `Municipio`).

---

## 4. Estructura del proyecto

```
precipitacion_chirps/
├── precipitacion_chirps.py     ← script principal
├── requirements.txt            ← dependencias
├── README.md
├── input/                      ← TÚ colocas aquí tu shapefile
│   ├── mis_subcuencas.shp
│   ├── mis_subcuencas.shx
│   ├── mis_subcuencas.dbf
│   └── mis_subcuencas.prj
└── output/                     ← se crea automáticamente al ejecutar
```

---

## 5. Instalación paso a paso

**Paso 1. Abre una terminal** (CMD, PowerShell o Terminal) dentro de la carpeta del proyecto:
```bash
cd "ruta\a\precipitacion_chirps"
```

**Paso 2. (Recomendado) Crea un entorno virtual** para no mezclar librerías con otros proyectos:
```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux / Mac
```

**Paso 3. Instala las librerías necesarias:**
```bash
pip install -r requirements.txt
```

Esto instala: `geopandas`, `rasterio`, `rasterstats`, `matplotlib`, `numpy`, `pandas`, `openpyxl`, `shapely`.

> 💡 Si `rasterio` falla al instalar en Windows, usa Conda:
> `conda install -c conda-forge rasterio geopandas rasterstats`

---

## 6. Cómo usar el script (paso a paso)

### Paso 1 — Coloca tu shapefile

Copia los 4 archivos de tu shapefile (`.shp`, `.shx`, `.dbf`, `.prj`) dentro de la carpeta `input/`.

### Paso 2 — (Opcional) Cambia el año a analizar

Abre `precipitacion_chirps.py` y modifica la línea:
```python
ANIO = 2024
```

### Paso 3 — Ejecuta el script

```bash
python precipitacion_chirps.py
```

### Paso 4 — Responde las preguntas interactivas

**Si hay un solo shapefile**, el script lo detecta automáticamente:
```
[OK] Shapefile detectado: input\mis_subcuencas.shp
```

**Si hay varios**, el script te pide elegir:
```
Se encontraron varios shapefiles en input/. Elige uno:
  1. input\subcuencas_valle.shp
  2. input\fincas_cafe.shp
Número del shapefile: 1
```

**Luego te muestra las columnas** del shapefile y te pide cuál usar como identificador:
```
Columnas disponibles en el shapefile:
   1. ID                 -> ejemplos: 1, 2, 3
   2. NOMBRE             -> ejemplos: Subcuenca A, Subcuenca B, Subcuenca C
   3. AREA_HA            -> ejemplos: 1523.4, 889.2, 2104.7

¿Qué columna identifica cada polígono? (nombre o número): 2
```

Puedes escribir **el nombre de la columna** (`NOMBRE`) o **el número** (`2`).

### Paso 5 — Espera el procesamiento

El script mostrará el progreso:
```
1. Cargando el shapefile desde input/...
2. Descargando CHIRPS mensual del año 2024...
   [01/12] descargando chirps-v2.0.2024.01.tif.gz ...
   [02/12] descargando chirps-v2.0.2024.02.tif.gz ...
   ...
3. Recortando y suavizando (bilineal x20)...
4. Calculando precipitación mensual promedio por subcuenca...
5. Generando gráficos (300 DPI)...
6. Exportando resultados numéricos a Excel...

PROCESO COMPLETADO CON EXITO
```

> ⏱️ **Tiempo estimado:** 3–8 minutos dependiendo de tu conexión.

### Paso 6 — Revisa los resultados en `output/`

---

## 7. Archivos generados (`output/`)

| Archivo | Descripción |
|---|---|
| `mapa_anual_precipitacion.png` | Mapa de calor con la precipitación acumulada anual (mm/año) |
| `mapas_mensuales_precipitacion.png` | Panel con los 12 mapas mensuales (escala unificada) |
| `barras_precipitacion.png` | Gráfico de barras del promedio regional mensual |
| `resultados_precipitacion_mensual.xlsx` | Tabla Excel con 14 columnas: ID, Ene–Dic y Total_Anual_mm |

---

## 8. Solución de problemas

| Problema | Causa / Solución |
|---|---|
| `No se encontró ningún .shp dentro de input/` | Verifica que los 4 archivos del shapefile estén en `input/` |
| Error de descarga / `HTTPError` | Revisa tu conexión; el servidor de UCSB puede estar caído temporalmente |
| `rasterio` no instala en Windows | Usa `conda install -c conda-forge rasterio` |
| Valores `NaN` en el Excel | El polígono está fuera de la cobertura de CHIRPS (más allá de 50°N o 50°S) |
| El acumulado anual se ve muy bajo | Revisa que el año configurado sea correcto y que el shapefile esté en la zona esperada |
