# Textura del Suelo por Polígono (SoilGrids) — Python

Script en Python que consulta los mapas globales de **SoilGrids 2.0** para calcular la composición de **arena, limo y arcilla** en la capa superficial (0–5 cm), clasifica la **textura según el triángulo USDA** y genera mapas y un Excel por polígono.

---

## 1. ¿Qué hace este script?

1. Lee tu shapefile (subcuencas, fincas, parcelas…).
2. Se conecta a los servidores de ISRIC mediante **VRT (Virtual Raster Tables)** — lee solo los píxeles que necesita, sin descargar archivos gigantes.
3. Calcula el **promedio y desviación estándar** de arena, limo y arcilla por polígono.
4. Clasifica la textura de cada polígono en una de las **12 clases USDA** mediante *point-in-polygon* sobre el triángulo textural.
5. Genera mapas espaciales, el triángulo USDA con tus puntos superpuestos y un gráfico de barras apiladas.

---

## 2. Fuente de información: SoilGrids 2.0

**SoilGrids** es el producto de referencia para mapeo global de propiedades del suelo, generado mediante *Machine Learning* a partir de más de 240.000 perfiles de suelo reales.

| Característica | Valor |
|---|---|
| Institución | **ISRIC — World Soil Information** (Países Bajos) |
| Resolución espacial | 250 metros |
| Cobertura geográfica | Global |
| Profundidad consultada | **0–5 cm** (capa superficial) |
| Variables usadas | `sand` (arena), `silt` (limo), `clay` (arcilla) |
| Unidades originales | g/kg → convertidas automáticamente a **%** (dividiendo entre 10) |
| Tipo de dato | **Mapa predictivo** (Machine Learning sobre perfiles + covariables ambientales) |
| CRS nativo | Homolosine de Goode (`+proj=igh`) — el script reproyecta automáticamente |
| Acceso | VRT remoto: `https://files.isric.org/soilgrids/latest/data/` |

**Más información:** <https://www.isric.org/explore/soilgrids>

### Clases USDA que reporta el script

Arcilloso, Arcillo-limoso, Franco arcillo-limoso, Arcillo-arenoso, Franco arcillo-arenoso, Franco arcilloso, Limoso, Franco limoso, Franco, Franco arenoso, Arenoso franco, Arenoso.

---

## 3. Requisitos previos

- **Python 3.9+**
- **GDAL** instalado en el sistema (viene con `rasterio`; en Windows se recomienda Conda).
- **Conexión a internet estable** (el acceso VRT lee fragmentos de ~250 m del servidor de ISRIC).
- Un **shapefile** con tus polígonos.

---

## 4. Estructura del proyecto

```
textura_suelo_soilgrids_py/
├── textura_suelo_soilgrids.py  ← script principal
├── README.md
├── input/                      ← TÚ colocas aquí tu shapefile
└── output/                     ← se crea automáticamente
```

---

## 5. Instalación paso a paso

**Paso 1. Abre una terminal en la carpeta del proyecto:**
```bash
cd "ruta\a\textura_suelo_soilgrids_py"
```

**Paso 2. (Recomendado) Entorno virtual:**
```bash
python -m venv venv
venv\Scripts\activate        # Windows
```

**Paso 3. Instala las dependencias:**
```bash
pip install geopandas rasterio rasterstats matplotlib numpy pandas openpyxl shapely
```

> 💡 Si en Windows `rasterio` o `gdal` dan error:
> `conda install -c conda-forge gdal rasterio geopandas rasterstats shapely`

---

## 6. Cómo usar el script (paso a paso)

### Paso 1 — Coloca tu shapefile en `input/`

### Paso 2 — Ejecuta

```bash
python textura_suelo_soilgrids.py
```

### Paso 3 — Elige la columna identificadora

```
Columnas disponibles en el shapefile:
   1. ID        -> ejemplos: 1, 2, 3
   2. NOMBRE    -> ejemplos: Finca A, Finca B, Finca C

¿Qué columna identifica cada polígono? (nombre o número): NOMBRE
```

### Paso 4 — Espera el procesamiento

```
1. Cargando el shapefile desde input/...
2. Conectando al servidor estático de SoilGrids...
3. Transformando el polígono al CRS nativo de SoilGrids...
4. Extrayendo estadísticas zonales por sub-polígono...
   → Procesando sand...
   → Procesando silt...
   → Procesando clay...
5. Calculando promedios y desviación estándar por subcuenca...

RESULTADOS FINALES
  Finca A:
    Arena:   42.30% (±4.51)
    Limo:    38.70% (±3.12)
    Arcilla: 19.00% (±2.45)
    Clase:   Franco (Loam)
```

> ⏱️ **Tiempo estimado:** 1–5 minutos dependiendo del tamaño y número de polígonos.

---

## 7. Archivos generados (`output/`)

| Archivo | Descripción |
|---|---|
| `resultados_textura_subcuencas.xlsx` | Tabla con ID, %Arena, SD, %Limo, SD, %Arcilla, SD y clase USDA |
| `mapas_textura_publicacion.png` | 4 paneles: mapa de arena, limo, arcilla + triángulo USDA con puntos |
| `grafico_barras_subcuencas.png` | Barras apiladas (arena/limo/arcilla) por polígono |

---

## 8. Interpretación rápida

- **Sumar las tres fracciones debe dar ≈ 100%**. Si no, hay píxeles NoData — el script los filtra automáticamente.
- La **clase textural** proviene del triángulo oficial USDA (idéntico al que usa el paquete `soiltexture` de R).
- El script usa `all_touched=False` (solo centroides dentro del polígono), igual que `terra::extract()` en R.

---

## 9. Solución de problemas

| Problema | Causa / Solución |
|---|---|
| `No se encontró ningún .shp dentro de input/` | Copia los 4 archivos del shapefile a `input/` |
| Descarga muy lenta o timeout | Es normal con polígonos grandes; el acceso VRT es por internet |
| `"Sin datos"` en algún polígono | Polígono sobre agua o fuera de cobertura SoilGrids |
| `rasterio` no instala en Windows | Usa Conda: `conda install -c conda-forge gdal rasterio` |
| Advertencias sobre CRS | El script ya reproyecta al CRS Homolosine de SoilGrids — son informativas |
