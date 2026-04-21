"""
Procesamiento genérico de temperatura ERA5-Land por polígonos.

Flujo interactivo:
  1. Detecta un shapefile dentro de la carpeta `input/`.
  2. Pide al usuario qué columna usar como identificador del polígono.
  3. Pide año inicial y año final a descargar.
  4. Descarga ERA5-Land mensual (t2m) desde Copernicus CDS.
  5. Recorta, calcula temperaturas medias por polígono y genera CSVs + figuras.

Requisitos:
  - Credenciales CDS configuradas en ~/.cdsapirc o en las variables
    CDS_URL y CDS_KEY de este script.
  - Dependencias en requirements.txt.
"""

import os
import sys
import glob
import zipfile
import warnings

import matplotlib
matplotlib.use("Agg")  # Backend no interactivo (evita abrir ventanas)
import matplotlib.pyplot as plt

import numpy as np
import pandas as pd
import xarray as xr
import geopandas as gpd
import rioxarray  # noqa: F401 (registra .rio en xarray)
import cdsapi

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
SCRIPT_DIR        = os.path.dirname(os.path.abspath(__file__))
DIR_INPUT         = os.path.join(SCRIPT_DIR, "input")
DIR_OUTPUT        = os.path.join(SCRIPT_DIR, "output")
DIR_DATOS         = os.path.join(DIR_OUTPUT, "datos")      # GRIBs descargados (cache)

# Credenciales CDS (opcional: si ~/.cdsapirc existe, se usa ese)
CDS_URL = "https://cds.climate.copernicus.eu/api"
CDS_KEY = "a6d83b65-7c6e-49a4-b3af-e222ce3fbdc5"

BUFFER_GRADOS = 0.2   # colchón alrededor del bbox para la descarga
ANIO_MIN_ERA5 = 1950  # rango válido aproximado de ERA5-Land
ANIO_MAX_ERA5 = 2025


# ---------------------------------------------------------------------------
# Utilidades de interacción
# ---------------------------------------------------------------------------
def encontrar_shapefile():
    """Busca shapefiles dentro de `input/` (incluye un nivel de subcarpetas)."""
    if not os.path.isdir(DIR_INPUT):
        os.makedirs(DIR_INPUT, exist_ok=True)

    patrones = [
        os.path.join(DIR_INPUT, "*.shp"),
        os.path.join(DIR_INPUT, "*", "*.shp"),
    ]
    encontrados = []
    for p in patrones:
        encontrados.extend(glob.glob(p))
    encontrados = sorted(set(encontrados))

    if not encontrados:
        print(f"[ERROR] No se encontró ningún shapefile (.shp) en: {DIR_INPUT}")
        print("        Coloca tu shapefile (con .shp, .shx, .dbf, .prj) en esa carpeta y vuelve a ejecutar.")
        sys.exit(1)

    if len(encontrados) == 1:
        print(f"[OK] Shapefile detectado: {os.path.relpath(encontrados[0], SCRIPT_DIR)}")
        return encontrados[0]

    print("Se encontraron varios shapefiles en input/. Elige uno:")
    for i, ruta in enumerate(encontrados, 1):
        print(f"  {i}. {os.path.relpath(ruta, SCRIPT_DIR)}")
    while True:
        resp = input("Número del shapefile a usar: ").strip()
        if resp.isdigit() and 1 <= int(resp) <= len(encontrados):
            return encontrados[int(resp) - 1]
        print("Entrada inválida. Intenta de nuevo.")


def elegir_columna(gdf):
    """Muestra las columnas del shapefile y pide al usuario cuál es el ID del polígono."""
    cols = [c for c in gdf.columns if c.lower() != "geometry"]
    print("\nColumnas disponibles en el shapefile:")
    for i, c in enumerate(cols, 1):
        muestra = gdf[c].dropna().astype(str).head(3).tolist()
        muestra_txt = ", ".join(muestra) if muestra else "(sin datos)"
        print(f"  {i:2d}. {c}   -> ejemplos: {muestra_txt}")

    while True:
        resp = input("\n¿Qué columna identifica cada polígono? (nombre o número): ").strip()
        if not resp:
            continue
        if resp.isdigit():
            idx = int(resp)
            if 1 <= idx <= len(cols):
                return cols[idx - 1]
        elif resp in cols:
            return resp
        print("Entrada inválida. Intenta de nuevo.")


def pedir_anios():
    """Pide año inicial y año final, validando contra el rango de ERA5-Land."""
    while True:
        try:
            a_ini = int(input(f"\nAño inicial ({ANIO_MIN_ERA5}-{ANIO_MAX_ERA5}): ").strip())
            a_fin = int(input(f"Año final   ({ANIO_MIN_ERA5}-{ANIO_MAX_ERA5}): ").strip())
        except ValueError:
            print("Debes ingresar enteros.")
            continue
        if not (ANIO_MIN_ERA5 <= a_ini <= ANIO_MAX_ERA5):
            print("Año inicial fuera de rango.")
            continue
        if not (ANIO_MIN_ERA5 <= a_fin <= ANIO_MAX_ERA5):
            print("Año final fuera de rango.")
            continue
        if a_fin < a_ini:
            print("El año final debe ser >= al año inicial.")
            continue
        return a_ini, a_fin


# ---------------------------------------------------------------------------
# Descarga ERA5-Land
# ---------------------------------------------------------------------------
def obtener_bbox(gdf, buffer=BUFFER_GRADOS):
    """Devuelve bbox [N, W, S, E] en lat/lon con colchón."""
    gdf_wgs = gdf.to_crs(epsg=4326)
    minx, miny, maxx, maxy = gdf_wgs.total_bounds
    return [maxy + buffer, minx - buffer, miny - buffer, maxx + buffer]


def configurar_cliente_cds():
    rc = os.path.join(os.path.expanduser("~"), ".cdsapirc")
    if os.path.exists(rc):
        return cdsapi.Client()
    return cdsapi.Client(url=CDS_URL, key=CDS_KEY)


def extraer_grib_de_zip(ruta_descarga, destino_grib):
    """Normaliza el resultado de la descarga a `destino_grib`.

    CDS a veces devuelve un ZIP que contiene el GRIB y a veces el GRIB directo.
    En ambos casos dejamos el archivo final en `destino_grib`.
    """
    if zipfile.is_zipfile(ruta_descarga):
        with zipfile.ZipFile(ruta_descarga, "r") as z:
            gribs = [n for n in z.namelist() if n.lower().endswith((".grib", ".grb"))]
            if not gribs:
                raise RuntimeError(f"El ZIP {ruta_descarga} no contiene ningún .grib")
            with z.open(gribs[0]) as fsrc, open(destino_grib, "wb") as fdst:
                fdst.write(fsrc.read())
        os.remove(ruta_descarga)
    else:
        # Es un GRIB directo: solo renombramos el .tmp al destino definitivo
        if os.path.abspath(ruta_descarga) != os.path.abspath(destino_grib):
            if os.path.exists(destino_grib):
                os.remove(destino_grib)
            os.rename(ruta_descarga, destino_grib)
    return destino_grib


def descargar_era5_land(anio_ini, anio_fin, bbox):
    """Descarga un GRIB mensual por año en DIR_DATOS. Salta los que ya existen."""
    os.makedirs(DIR_DATOS, exist_ok=True)
    client = configurar_cliente_cds()
    meses = [f"{m:02d}" for m in range(1, 13)]

    archivos = []
    for anio in range(anio_ini, anio_fin + 1):
        destino = os.path.join(DIR_DATOS, f"era5land_t2m_{anio}.grib")
        archivos.append(destino)
        if os.path.exists(destino) and os.path.getsize(destino) > 0:
            print(f"  [skip] {os.path.basename(destino)} ya existe")
            continue

        print(f"  [descargando] {anio} ...")
        tmp = destino + ".tmp"
        client.retrieve(
            "reanalysis-era5-land-monthly-means",
            {
                "variable": "2m_temperature",
                "product_type": "monthly_averaged_reanalysis",
                "year": str(anio),
                "month": meses,
                "time": "00:00",
                "area": bbox,  # [N, W, S, E]
                "data_format": "grib",
                "download_format": "unarchived",
            },
            tmp,
        )
        extraer_grib_de_zip(tmp, destino)
    return archivos


# ---------------------------------------------------------------------------
# Procesamiento
# ---------------------------------------------------------------------------
def cargar_gribs(rutas):
    """Carga y concatena los GRIBs descargados en un único xarray.DataArray (t2m en °C)."""
    datasets = []
    for r in rutas:
        if not os.path.exists(r):
            continue
        ds = xr.open_dataset(r, engine="cfgrib", backend_kwargs={"indexpath": ""})
        datasets.append(ds)
    if not datasets:
        raise RuntimeError("No se pudo cargar ningún archivo GRIB.")
    ds = xr.concat(datasets, dim="time") if len(datasets) > 1 else datasets[0]

    # Variable puede llamarse t2m o 2t dependiendo de la versión de cfgrib
    nombre_var = "t2m" if "t2m" in ds.variables else [v for v in ds.data_vars][0]
    da = ds[nombre_var] - 273.15  # K -> °C
    da.attrs["units"] = "degC"
    da = da.rename("t2m")

    # Asegurar nombres estándar de coordenadas y CRS
    if "longitude" in da.coords:
        da = da.rename({"longitude": "x", "latitude": "y"})
    da = da.sortby("y")
    da = da.rio.write_crs("EPSG:4326", inplace=False)
    return da


def recortar_a_poligono(da, geom):
    try:
        return da.rio.clip([geom], crs="EPSG:4326", all_touched=True, drop=True)
    except Exception:
        return None


def procesar_por_poligono(da, gdf, columna_id):
    """Devuelve un DataFrame (index=tiempo, columnas=polígonos) con T media mensual."""
    series = {}
    total = len(gdf)
    for i, row in gdf.iterrows():
        nombre = str(row[columna_id])
        recorte = recortar_a_poligono(da, row.geometry)
        if recorte is None or recorte.size == 0:
            continue
        serie = recorte.mean(dim=("x", "y"), skipna=True).to_pandas()
        series[nombre] = serie
        if (i + 1) % 25 == 0 or (i + 1) == total:
            print(f"  procesados {i + 1}/{total} polígonos")

    if not series:
        raise RuntimeError("Ningún polígono produjo datos (¿bbox/shape fuera del dominio?).")

    df = pd.concat(series, axis=1)
    df.index.name = "fecha"
    return df


# ---------------------------------------------------------------------------
# Exportación y figuras
# ---------------------------------------------------------------------------
def calcular_series_anuales(df):
    """Devuelve dos DataFrames anuales (media y amplitud) con filas=año, columnas=polígono."""
    idx = pd.to_datetime(df.index)
    anual_media = df.groupby(idx.year).mean()
    anual_media.index.name = "anio"

    anual_min = df.groupby(idx.year).min()
    anual_max = df.groupby(idx.year).max()
    anual_amplitud = anual_max - anual_min
    anual_amplitud.index.name = "anio"
    return anual_media, anual_amplitud


def construir_anual_largo(anual_media, anual_min, anual_max):
    """Convierte los DataFrames anuales a formato largo: anio, poligono, t_media, t_min, t_max."""
    filas = []
    for anio in anual_media.index:
        for poligono in anual_media.columns:
            filas.append({
                "anio": int(anio),
                "poligono": poligono,
                "t_media":  anual_media.loc[anio, poligono],
                "t_min":    anual_min.loc[anio, poligono],
                "t_max":    anual_max.loc[anio, poligono],
                "amplitud": anual_max.loc[anio, poligono] - anual_min.loc[anio, poligono],
            })
    return pd.DataFrame(filas)


def exportar_excel(df, gdf, columna_id):
    """Genera un único .xlsx con varias hojas + un resumen anual en formato largo."""
    os.makedirs(DIR_OUTPUT, exist_ok=True)

    # Agregaciones anuales
    idx = pd.to_datetime(df.index)
    anual_media = df.groupby(idx.year).mean()
    anual_media.index.name = "anio"
    anual_min = df.groupby(idx.year).min()
    anual_min.index.name = "anio"
    anual_max = df.groupby(idx.year).max()
    anual_max.index.name = "anio"
    anual_amplitud = anual_max - anual_min
    anual_amplitud.index.name = "anio"

    # Resumen global por polígono
    resumen = pd.DataFrame({
        "poligono": df.columns,
        "t_media":  df.mean(axis=0).values,
        "t_min":    df.min(axis=0).values,
        "t_max":    df.max(axis=0).values,
        "amplitud": (df.max(axis=0) - df.min(axis=0)).values,
    })

    # Resumen anual en formato largo (una fila por año y polígono)
    anual_largo = construir_anual_largo(anual_media, anual_min, anual_max)

    ruta_xlsx = os.path.join(DIR_OUTPUT, "temperatura_resultados.xlsx")
    with pd.ExcelWriter(ruta_xlsx, engine="openpyxl") as writer:
        df.round(3).to_excel(writer, sheet_name="mensual")
        anual_media.round(3).to_excel(writer, sheet_name="anual_media")
        anual_min.round(3).to_excel(writer, sheet_name="anual_min")
        anual_max.round(3).to_excel(writer, sheet_name="anual_max")
        anual_amplitud.round(3).to_excel(writer, sheet_name="anual_amplitud")
        anual_largo.round(3).to_excel(writer, sheet_name="anual_largo", index=False)
        resumen.round(3).to_excel(writer, sheet_name="resumen_global", index=False)
    print(f"  [ok] {os.path.relpath(ruta_xlsx, SCRIPT_DIR)}")
    print(f"       Hojas: mensual, anual_media, anual_min, anual_max, anual_amplitud, anual_largo, resumen_global")

    return resumen, anual_media


def figura_series(df, maximo=20):
    """Series temporales (máximo N polígonos por legibilidad)."""
    fig, ax = plt.subplots(figsize=(12, 6))
    cols = df.columns[:maximo]
    for c in cols:
        ax.plot(df.index, df[c], label=str(c), linewidth=0.9)
    ax.set_title(f"Serie mensual de temperatura (primeros {len(cols)} polígonos)")
    ax.set_xlabel("Fecha")
    ax.set_ylabel("Temperatura media (°C)")
    if len(cols) <= 15:
        ax.legend(fontsize=7, ncol=2, loc="best")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    out = os.path.join(DIR_OUTPUT, "figura_series.png")
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"  [ok] {os.path.relpath(out, SCRIPT_DIR)}")


def figura_mapa(gdf, resumen, columna_id):
    """Mapa coroplético con temperatura media por polígono."""
    gdf_plot = gdf.merge(resumen, left_on=columna_id, right_on="poligono", how="left")
    fig, ax = plt.subplots(figsize=(10, 10))
    gdf_plot.plot(
        column="t_media",
        cmap="RdYlBu_r",
        legend=True,
        legend_kwds={"label": "Temperatura media (°C)", "shrink": 0.7},
        edgecolor="black",
        linewidth=0.2,
        ax=ax,
    )
    ax.set_title("Temperatura media por polígono")
    ax.set_axis_off()
    fig.tight_layout()
    out = os.path.join(DIR_OUTPUT, "figura_mapa_media.png")
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"  [ok] {os.path.relpath(out, SCRIPT_DIR)}")


def figura_series_anuales(anual_media, maximo=20):
    """Serie anual de la media (hasta N polígonos)."""
    fig, ax = plt.subplots(figsize=(12, 6))
    cols = anual_media.columns[:maximo]
    for c in cols:
        ax.plot(anual_media.index, anual_media[c], marker="o", markersize=3,
                linewidth=1.0, label=str(c))
    ax.set_title(f"Temperatura media anual (primeros {len(cols)} polígonos)")
    ax.set_xlabel("Año")
    ax.set_ylabel("Temperatura media anual (°C)")
    if len(cols) <= 15:
        ax.legend(fontsize=7, ncol=2, loc="best")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    out = os.path.join(DIR_OUTPUT, "figura_series_anuales.png")
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"  [ok] {os.path.relpath(out, SCRIPT_DIR)}")


def figura_boxplot(df, topn=20):
    """Boxplot: si hay muchos polígonos, toma los topN con mayor amplitud."""
    if df.shape[1] > topn:
        amplitudes = (df.max() - df.min()).sort_values(ascending=False)
        cols = amplitudes.head(topn).index
        titulo = f"Distribución mensual - top {topn} polígonos por amplitud"
    else:
        cols = df.columns
        titulo = "Distribución mensual por polígono"

    fig, ax = plt.subplots(figsize=(max(8, len(cols) * 0.4), 6))
    df[cols].plot.box(ax=ax, rot=75)
    ax.set_title(titulo)
    ax.set_ylabel("Temperatura (°C)")
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    out = os.path.join(DIR_OUTPUT, "figura_boxplot.png")
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"  [ok] {os.path.relpath(out, SCRIPT_DIR)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 70)
    print("  ERA5-Land: temperatura mensual por polígono (procesamiento genérico)")
    print("=" * 70)

    # 1. Shapefile y columna
    ruta_shp = encontrar_shapefile()
    print(f"\n[1/5] Cargando shapefile ...")
    gdf = gpd.read_file(ruta_shp)
    if gdf.crs is None:
        print("[WARN] El shapefile no tiene CRS definido. Asumiendo EPSG:4326.")
        gdf = gdf.set_crs(epsg=4326)
    gdf = gdf.to_crs(epsg=4326)
    print(f"       Polígonos encontrados: {len(gdf)}")

    columna_id = elegir_columna(gdf)
    print(f"       Columna ID seleccionada: {columna_id}")

    # 2. Rango de años
    anio_ini, anio_fin = pedir_anios()
    print(f"       Rango: {anio_ini}-{anio_fin}  ({anio_fin - anio_ini + 1} años)")

    # 3. Descarga
    print(f"\n[2/5] Descargando ERA5-Land a {os.path.relpath(DIR_DATOS, SCRIPT_DIR)}/ ...")
    bbox = obtener_bbox(gdf)
    print(f"       BBox [N,W,S,E]: {[round(x, 3) for x in bbox]}")
    archivos = descargar_era5_land(anio_ini, anio_fin, bbox)

    # 4. Carga y procesamiento
    print(f"\n[3/5] Cargando GRIBs ...")
    da = cargar_gribs(archivos)
    print(f"       Tiempos: {da.sizes.get('time', '?')}   Grilla: {da.sizes.get('y','?')}x{da.sizes.get('x','?')}")

    print(f"\n[4/5] Calculando series por polígono ...")
    df = procesar_por_poligono(da, gdf, columna_id)

    # 5. Exportación
    print(f"\n[5/5] Generando Excel y figuras en {os.path.relpath(DIR_OUTPUT, SCRIPT_DIR)}/ ...")
    resumen, anual_media = exportar_excel(df, gdf, columna_id)
    figura_series(df)
    figura_series_anuales(anual_media)
    figura_mapa(gdf, resumen, columna_id)
    figura_boxplot(df)

    print("\n[FIN] Proceso completado correctamente.")


if __name__ == "__main__":
    main()
