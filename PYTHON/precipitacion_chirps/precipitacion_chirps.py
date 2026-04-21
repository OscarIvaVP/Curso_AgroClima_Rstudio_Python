"""
================================================================================
SCRIPT PARA ANÁLISIS AGROCLIMÁTICO: PRECIPITACIÓN (CHIRPS v2.0)
Descarga directa de GeoTIFFs mensuales de CHIRPS y análisis por subcuenca
================================================================================

Fuente: Climate Hazards Group InfraRed Precipitation with Station data (CHIRPS)
        UCSB Climate Hazards Center
Resolución: 0.05° (~5 km)
Frecuencia: mensual (mm/mes)

Dependencias:
    pip install geopandas rasterio rasterstats matplotlib numpy pandas openpyxl

Genera:
    - mapa_anual_precipitacion.png      (lluvia acumulada anual)
    - mapas_mensuales_precipitacion.png (12 mapas con escala unificada)
    - barras_precipitacion.png          (promedio regional mensual)
    - resultados_precipitacion_mensual.xlsx  (tabla por subcuenca)
================================================================================
"""

import glob
import gzip
import os
import shutil
import sys
import tempfile
import urllib.request

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from matplotlib.colors import Normalize
from rasterio.features import geometry_mask
from rasterio.mask import mask as rio_mask
from rasterio.transform import Affine
from rasterio.warp import Resampling, reproject
from rasterstats import zonal_stats

# =============================================================================
# CONVENCIONES DEL PROYECTO
# =============================================================================
#   - input/   : el usuario crea la carpeta y pone ahí el shapefile
#   - output/  : el script la crea y escribe todos los resultados ahí
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DIR_INPUT  = os.path.join(SCRIPT_DIR, "input")
DIR_OUTPUT = os.path.join(SCRIPT_DIR, "output")

ANIO = 2024
URL_BASE = "https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_monthly/tifs"
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
         "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
NODATA_CHIRPS = -9999.0
FACTOR_UPSAMPLE = 20  # remuestreo bilineal (equivalente a disagg fact=20 en R)


# =============================================================================
# UTILIDADES
# =============================================================================
def encontrar_shapefile():
    """Detecta un .shp en input/ (cualquier nombre, hasta 1 nivel de subcarpetas)."""
    if not os.path.isdir(DIR_INPUT):
        print(f"[ERROR] No existe {DIR_INPUT}/. Créala y coloca ahí tu shapefile.")
        sys.exit(1)
    patrones = [os.path.join(DIR_INPUT, "*.shp"),
                os.path.join(DIR_INPUT, "*", "*.shp")]
    encontrados = sorted({p for pat in patrones for p in glob.glob(pat)})
    if not encontrados:
        print(f"[ERROR] No se encontró ningún .shp dentro de {DIR_INPUT}/")
        sys.exit(1)
    if len(encontrados) == 1:
        print(f"[OK] Shapefile detectado: {os.path.relpath(encontrados[0], SCRIPT_DIR)}")
        return encontrados[0]
    print("Se encontraron varios shapefiles en input/. Elige uno:")
    for i, ruta in enumerate(encontrados, 1):
        print(f"  {i}. {os.path.relpath(ruta, SCRIPT_DIR)}")
    while True:
        resp = input("Número del shapefile: ").strip()
        if resp.isdigit() and 1 <= int(resp) <= len(encontrados):
            return encontrados[int(resp) - 1]
        print("Entrada inválida.")


def elegir_columna(gdf):
    """Lista columnas del shapefile y pide al usuario cuál es el ID del polígono."""
    cols = [c for c in gdf.columns if c.lower() != "geometry"]
    print("\nColumnas disponibles en el shapefile:")
    for i, c in enumerate(cols, 1):
        muestra = ", ".join(gdf[c].dropna().astype(str).head(3).tolist()) or "(sin datos)"
        print(f"  {i:2d}. {c:20s} -> ejemplos: {muestra}")
    while True:
        resp = input("\n¿Qué columna identifica cada polígono? (nombre o número): ").strip()
        if not resp:
            continue
        if resp.isdigit() and 1 <= int(resp) <= len(cols):
            return cols[int(resp) - 1]
        if resp in cols:
            return resp
        print("Entrada inválida.")


# =============================================================================
# 1. CARGAR SHAPEFILE
# =============================================================================
print("1. Cargando el shapefile desde input/...")
ruta_shp = encontrar_shapefile()
poligono = gpd.read_file(ruta_shp).to_crs("EPSG:4326")
col_id = elegir_columna(poligono)
nombres_subc = poligono[col_id].astype(str).tolist()
geoms = list(poligono.geometry.values)
os.makedirs(DIR_OUTPUT, exist_ok=True)
print(f"   Polígonos detectados ({col_id}): {len(nombres_subc)}")

# Rutas de salida (todas bajo output/)
OUT_EXCEL = os.path.join(DIR_OUTPUT, "resultados_precipitacion_mensual.xlsx")
OUT_MAPA_ANUAL = os.path.join(DIR_OUTPUT, "mapa_anual_precipitacion.png")
OUT_MAPAS_MENSUALES = os.path.join(DIR_OUTPUT, "mapas_mensuales_precipitacion.png")
OUT_BARRAS = os.path.join(DIR_OUTPUT, "barras_precipitacion.png")

# =============================================================================
# 2. DESCARGAR 12 GEOTIFFs DE CHIRPS
# =============================================================================
print(f"2. Descargando CHIRPS mensual del año {ANIO}...")
tmpdir = tempfile.mkdtemp(prefix="chirps_")
tif_mensuales = []
for m in range(1, 13):
    nombre = f"chirps-v2.0.{ANIO}.{m:02d}.tif"
    url = f"{URL_BASE}/{nombre}.gz"
    gz_path = os.path.join(tmpdir, nombre + ".gz")
    tif_path = os.path.join(tmpdir, nombre)
    print(f"   [{m:02d}/12] descargando {nombre}.gz ...")
    urllib.request.urlretrieve(url, gz_path)
    with gzip.open(gz_path, "rb") as fin, open(tif_path, "wb") as fout:
        shutil.copyfileobj(fin, fout)
    tif_mensuales.append(tif_path)

# =============================================================================
# 3. RECORTAR + REMUESTREAR BILINEAL (fact=20) + ENMASCARAR
# =============================================================================
print(f"3. Recortando y suavizando (bilineal x{FACTOR_UPSAMPLE})...")


def upsample_bilinear(src_array, src_transform, factor):
    """Remuestrea un array 2D por `factor` con interpolación bilineal."""
    h, w = src_array.shape
    new_h, new_w = h * factor, w * factor
    new_transform = Affine(
        src_transform.a / factor, src_transform.b, src_transform.c,
        src_transform.d, src_transform.e / factor, src_transform.f,
    )
    dest = np.full((new_h, new_w), np.nan, dtype="float32")
    reproject(
        source=np.ascontiguousarray(src_array),
        destination=dest,
        src_transform=src_transform,
        src_crs="EPSG:4326",
        dst_transform=new_transform,
        dst_crs="EPSG:4326",
        src_nodata=np.nan,
        dst_nodata=np.nan,
        resampling=Resampling.bilinear,
    )
    return dest, new_transform


stack = []
transform_ref = None
mascara_fuera = None
for tif in tif_mensuales:
    with rasterio.open(tif) as src:
        arr, tr = rio_mask(src, geoms, crop=True, nodata=np.nan, filled=True)
    banda = arr[0].astype("float32")
    banda[banda <= NODATA_CHIRPS + 1] = np.nan

    # Suavizado bilineal: los píxeles se vuelven ~20 veces más finos,
    # de modo que cualquier subcuenca (incluso pequeña) contiene muchos.
    banda_hd, tr_hd = upsample_bilinear(banda, tr, FACTOR_UPSAMPLE)

    # Recorte exacto al polígono en alta resolución
    if mascara_fuera is None:
        mascara_fuera = geometry_mask(
            geoms,
            transform=tr_hd,
            out_shape=banda_hd.shape,
            invert=False,  # True = fuera del polígono
        )
    banda_hd[mascara_fuera] = np.nan

    stack.append(banda_hd)
    transform_ref = tr_hd

stack = np.stack(stack, axis=0)  # (12, H_hd, W_hd)

# Extensión geográfica para matplotlib imshow
h, w = stack.shape[1], stack.shape[2]
x_min = transform_ref.c
y_max = transform_ref.f
x_max = x_min + w * transform_ref.a
y_min = y_max + h * transform_ref.e
extent = (x_min, x_max, y_min, y_max)

anual = np.nansum(stack, axis=0)
anual[np.all(np.isnan(stack), axis=0)] = np.nan

# =============================================================================
# 4. ZONAL STATS SOBRE EL RÁSTER REMUESTREADO (all_touched=True como respaldo)
# =============================================================================
print("4. Calculando precipitación mensual promedio por subcuenca...")
filas = []
for banda_hd in stack:
    # rasterstats no trata NaN como nodata: uso sentinela -9999 para el cálculo.
    banda_calc = np.where(np.isnan(banda_hd), -9999.0, banda_hd).astype("float32")
    stats = zonal_stats(
        poligono, banda_calc,
        affine=transform_ref,
        stats="mean",
        all_touched=True,  # toma cualquier pixel fino que toque el polígono
        nodata=-9999.0,
    )
    filas.append([s["mean"] if s["mean"] is not None else np.nan for s in stats])

matriz = np.array(filas).T  # (n_subc, 12)
tabla = pd.DataFrame(matriz, columns=MESES)
tabla.insert(0, col_id, nombres_subc)
tabla[MESES] = tabla[MESES].round(1)
tabla["Total_Anual_mm"] = tabla[MESES].sum(axis=1).round(1)

# =============================================================================
# 5. GRÁFICOS
# =============================================================================
print("5. Generando gráficos (300 DPI)...")
cmap_lluvia = "YlGnBu"  # Amarillo -> azul (paleta húmeda)


def dibujar_mapa_anual():
    fig, ax = plt.subplots(figsize=(9, 6), dpi=300)
    im = ax.imshow(anual, cmap=cmap_lluvia, extent=extent, origin="upper")
    poligono.boundary.plot(ax=ax, color="#333333", linewidth=1.2)
    ax.set_title(f"Precipitación Acumulada Anual {ANIO} (mm/año)",
                 fontsize=13, fontweight="bold")
    ax.set_xticks([])
    ax.set_yticks([])
    for side in ax.spines.values():
        side.set_visible(False)
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("mm", rotation=0, labelpad=10)
    fig.tight_layout()
    fig.savefig(OUT_MAPA_ANUAL, dpi=300, bbox_inches="tight")
    plt.close(fig)


def dibujar_mapas_mensuales():
    vmin = np.nanmin(stack)
    vmax = np.nanmax(stack)
    norm = Normalize(vmin=vmin, vmax=vmax)

    fig, axes = plt.subplots(3, 4, figsize=(12, 8), dpi=300)
    for i, ax in enumerate(axes.flat):
        ax.imshow(stack[i], cmap=cmap_lluvia, norm=norm,
                  extent=extent, origin="upper")
        poligono.boundary.plot(ax=ax, color="#333333", linewidth=0.8)
        ax.set_title(MESES[i], fontsize=11)
        ax.set_xticks([])
        ax.set_yticks([])
        for side in ax.spines.values():
            side.set_visible(False)

    fig.suptitle(f"Evolución Mensual de la Precipitación (CHIRPS {ANIO})",
                 fontsize=15, fontweight="bold", y=0.98)

    sm = plt.cm.ScalarMappable(cmap=cmap_lluvia, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=axes.ravel().tolist(),
                        fraction=0.025, pad=0.02)
    cbar.set_label("mm/mes")

    fig.savefig(OUT_MAPAS_MENSUALES, dpi=300, bbox_inches="tight")
    plt.close(fig)


def dibujar_barras():
    promedio_regional = tabla[MESES].mean(axis=0).values
    fig, ax = plt.subplots(figsize=(9, 5.5), dpi=300)
    barras = ax.bar(MESES, promedio_regional,
                    color="steelblue", edgecolor="midnightblue")
    ax.plot(MESES, promedio_regional, color="midnightblue",
            linewidth=2, linestyle="--", marker="o")
    for rect, valor in zip(barras, promedio_regional):
        ax.text(rect.get_x() + rect.get_width() / 2,
                rect.get_height() + max(promedio_regional) * 0.02,
                f"{valor:.0f}", ha="center", fontsize=9)
    ax.set_title(f"Precipitación Mensual Promedio Regional ({ANIO})",
                 fontsize=13, fontweight="bold")
    ax.set_ylabel("Precipitación (mm/mes)")
    ax.set_ylim(0, max(promedio_regional) * 1.2)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT_BARRAS, dpi=300, bbox_inches="tight")
    plt.close(fig)


dibujar_mapa_anual()
dibujar_mapas_mensuales()
dibujar_barras()

# =============================================================================
# 6. EXPORTAR EXCEL
# =============================================================================
print("6. Exportando resultados numéricos a Excel...")
tabla.to_excel(OUT_EXCEL, index=False)

# Limpieza de archivos temporales descargados
shutil.rmtree(tmpdir, ignore_errors=True)

print("\n====================================================")
print("PROCESO COMPLETADO CON EXITO")
print("Archivos generados:")
print(f"  1. Mapa anual:      {OUT_MAPA_ANUAL}")
print(f"  2. Mapas 12 meses:  {OUT_MAPAS_MENSUALES}")
print(f"  3. Barras:          {OUT_BARRAS}")
print(f"  4. Excel:           {OUT_EXCEL}")
print("====================================================")
