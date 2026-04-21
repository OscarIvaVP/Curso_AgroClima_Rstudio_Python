# Temperatura Media por Polígono (ERA5-Land) — Python

Script interactivo en Python que descarga datos de **temperatura del aire a 2 m (ERA5-Land)** desde el Climate Data Store (CDS) de Copernicus, calcula series mensuales y anuales por polígono y genera mapas, gráficos y un Excel multi-hoja.

---

## 1. ¿Qué hace este script?

1. Lee tu shapefile (subcuencas, fincas, municipios…).
2. Te pregunta **qué rango de años** quieres analizar (ej: 2000–2024).
3. Descarga los archivos **GRIB mensuales** de ERA5-Land del CDS para ese rango y el bbox de tu área.
4. Convierte la temperatura de **Kelvin a °C**.
5. Calcula para cada polígono: temperatura media, mínima, máxima y amplitud (anual y global).
6. Produce mapas, series temporales, boxplots y un Excel con 7 hojas de resultados.

---

## 2. Fuente de información: ERA5-Land

**ERA5-Land** es un reanálisis climático global de alta resolución generado por Copernicus.

| Característica | Valor |
|---|---|
| Institución | Centro Europeo de Previsiones Meteorológicas a Plazo Medio (**ECMWF**) / Servicio de Cambio Climático de Copernicus (**C3S**) |
| Resolución espacial | 0.1° (~9 km × 9 km) |
| Cobertura geográfica | Global (áreas terrestres) |
| Serie temporal | Desde 1950 hasta ~2 meses antes del presente |
| Variable usada | `2m_temperature` (temperatura del aire a 2 m) |
| Unidades originales | Kelvin (K) → convertidas automáticamente a **°C** |
| Tipo de dato | **Reanálisis**: un modelo físico integra observaciones de satélites, globos sonda y estaciones |
| Formato | GRIB mensual (se descarga un archivo por año) |

**Más información:** <https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land-monthly-means>

---

## 3. Requisitos previos

### 3.1 Cuenta en Copernicus CDS (obligatorio)

1. Regístrate gratis en <https://cds.climate.copernicus.eu/>.
2. Confirma tu correo e inicia sesión.
3. Ve a **tu perfil → API Token** y copia tu **URL** y **KEY**.
4. Acepta los **Términos de uso** del dataset *ERA5-Land monthly averaged data* (si no los aceptas, las descargas fallarán).

### 3.2 Configurar las credenciales

**Opción A (recomendada)** — Crear el archivo `~/.cdsapirc`:

En Windows, crea el archivo `C:\Users\<tu_usuario>\.cdsapirc` con este contenido:
```
url: https://cds.climate.copernicus.eu/api
key: TU-CLAVE-AQUI
```

En Linux / Mac, crea `~/.cdsapirc` con el mismo contenido.

**Opción B** — Editar directamente el script y reemplazar:
```python
CDS_KEY = "TU-CLAVE-AQUI"
```

### 3.3 Otros requisitos

- **Python 3.9+**
- Un **shapefile** con los polígonos de análisis.
- Conexión a internet estable (las descargas CDS pueden tardar varios minutos por año).

---

## 4. Estructura del proyecto

```
temperatura_era5land/
├── temperatura_media.py        ← script principal
├── requirements.txt
├── README.md
├── input/                      ← TÚ colocas aquí tu shapefile
└── output/                     ← se crea automáticamente
    └── datos/                  ← caché de los GRIB descargados
```

---

## 5. Instalación paso a paso

**Paso 1. Abre una terminal en la carpeta del proyecto:**
```bash
cd "ruta\a\temperatura_era5land"
```

**Paso 2. (Recomendado) Crea un entorno virtual:**
```bash
python -m venv venv
venv\Scripts\activate        # Windows
```

**Paso 3. Instala las dependencias:**
```bash
pip install -r requirements.txt
```

Esto instala `cdsapi`, `xarray`, `cfgrib`, `eccodes`, `geopandas`, `rioxarray`, `matplotlib`, `pandas`, `numpy`, `openpyxl`, entre otros.

> 💡 **Conda alternativa** (más estable en Windows para leer GRIB):
> `conda install -c conda-forge cdsapi xarray cfgrib eccodes rioxarray geopandas`

---

## 6. Cómo usar el script (paso a paso)

### Paso 1 — Coloca el shapefile en `input/`

### Paso 2 — Ejecuta el script

```bash
python temperatura_media.py
```

### Paso 3 — Responde las preguntas interactivas

**Selección del shapefile** (si hay más de uno):
```
[OK] Shapefile detectado: input\subcuencas.shp
```

**Columna identificadora:**
```
Columnas disponibles en el shapefile:
   1. ID        -> ejemplos: 1, 2, 3
   2. NOMBRE    -> ejemplos: Alta, Media, Baja

¿Qué columna identifica cada polígono? (nombre o número): NOMBRE
```

**Rango de años:**
```
Año inicial (1950-2025): 2000
Año final   (1950-2025): 2024
```
> Cuantos más años, más tiempo tardará (un GRIB por año, ~10–60 s cada uno la primera vez).

### Paso 4 — Espera la descarga y el procesamiento

```
[1/5] Cargando shapefile ...
[2/5] Descargando ERA5-Land a output\datos/ ...
       BBox [N,W,S,E]: [5.8, -75.2, 3.1, -72.9]
       [descargando] 2000 ...
       [descargando] 2001 ...
       ...
[3/5] Cargando GRIBs ...
[4/5] Calculando series por polígono ...
[5/5] Generando Excel y figuras en output/ ...
[FIN] Proceso completado correctamente.
```

> ⏱️ **Primera ejecución:** ~1–2 minutos por año descargado.
> **Ejecuciones siguientes:** los GRIB quedan en caché (`output/datos/`) y se reutilizan.

---

## 7. Archivos generados (`output/`)

| Archivo | Descripción |
|---|---|
| `temperatura_resultados.xlsx` | Excel con **7 hojas**: `mensual`, `anual_media`, `anual_min`, `anual_max`, `anual_amplitud`, `anual_largo`, `resumen_global` |
| `figura_mapa_media.png` | Mapa coroplético con la temperatura media por polígono |
| `figura_series.png` | Serie temporal mensual (hasta 20 polígonos) |
| `figura_series_anuales.png` | Serie anual (hasta 20 polígonos) |
| `figura_boxplot.png` | Diagrama de caja por polígono (top 20 por amplitud) |
| `datos/era5land_t2m_AAAA.grib` | Archivos GRIB descargados (caché reutilizable) |

---

## 8. Solución de problemas

| Problema | Causa / Solución |
|---|---|
| `AuthenticationError` o `401` | Credenciales CDS incorrectas → revisa `~/.cdsapirc` |
| La descarga se queda en "queued" mucho tiempo | Normal: la cola del CDS puede tardar minutos. Déjalo correr. |
| `Required license not accepted` | Debes aceptar los términos del dataset en la web del CDS |
| `cfgrib` no puede leer el archivo | `conda install -c conda-forge eccodes cfgrib` |
| El shapefile no tiene CRS | El script asume `EPSG:4326` con advertencia; idealmente asigna un CRS en tu GIS |
| Valores extraños en °C (ej: -273) | La conversión Kelvin→°C falló; revisa el log por si la variable no es `t2m` |
| Quiero re-descargar un año | Borra el archivo correspondiente en `output/datos/` y vuelve a correr |
