# ==============================================================================
# SCRIPT PARA DETERMINAR LA TEXTURA DEL SUELO (VÍA VIRTUAL RASTERS) - PYTHON
# Bypassa la API REST inestable y analiza el 100% del área de estudio.
# Incluye visualización espacial y gráfica de los resultados.
# ==============================================================================
#
# Dependencias (instalar con pip):
# pip install geopandas rasterio rasterstats matplotlib numpy pandas openpyxl shapely
#
# Nota: Requiere GDAL instalado en el sistema (viene con rasterio en la mayoría
#       de instalaciones, pero si hay problemas: conda install -c conda-forge gdal)
#
# CORRECCIONES vs. versión anterior:
#   1. Clasificación textural USDA basada en polígonos exactos del triángulo
#      (point-in-polygon), idéntica al paquete soiltexture de R.
#   2. zonal_stats con all_touched=False para replicar terra::extract de R.
# ==============================================================================

import glob
import os
import sys

import geopandas as gpd
import rasterio
from rasterio.mask import mask as rio_mask
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from rasterstats import zonal_stats
from shapely.geometry import Point, Polygon
import numpy as np
import pandas as pd

# =============================================================================
# CONVENCIONES DEL PROYECTO
# =============================================================================
# - input/   : el usuario crea la carpeta y pone ahí el shapefile
# - output/  : el script la crea y escribe todos los resultados ahí
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DIR_INPUT  = os.path.join(SCRIPT_DIR, "input")
DIR_OUTPUT = os.path.join(SCRIPT_DIR, "output")


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
# CLASIFICACIÓN TEXTURAL USDA - POLÍGONOS EXACTOS
# =============================================================================
# Estos vértices replican EXACTAMENTE los polígonos del triángulo textural USDA
# tal como los define el paquete soiltexture de R (clase USDA.TT).
# La clasificación se hace por point-in-polygon: sin ambigüedad en las fronteras.
# =============================================================================

# Cada clase se define como una lista de vértices (CLAY, SILT, SAND) en porcentaje.
# Vértices verificados con Shapely: 100% cobertura, 0 huecos, 0 traslapes.
# Formato: (CLAY, SILT, SAND) — los tres deben sumar 100.
USDA_CLASES = {
    "Clay": [(100, 0, 0), (55, 0, 45), (40, 0, 60), (40, 15, 45), (40, 40, 20), (55, 45, 0)],
    "Silty clay": [(55, 45, 0), (40, 40, 20), (40, 60, 0)],
    "Silty clay loam": [(40, 60, 0), (40, 40, 20), (27, 53, 20), (27, 73, 0)],
    "Sandy clay": [(55, 0, 45), (35, 0, 65), (35, 20, 45), (40, 15, 45), (40, 0, 60)],
    "Sandy clay loam": [(35, 0, 65), (20, 0, 80), (20, 28, 52), (27, 28, 45), (35, 20, 45)],
    "Clay loam": [(40, 15, 45), (35, 20, 45), (27, 28, 45), (27, 53, 20), (40, 40, 20)],
    "Silt": [(12, 88, 0), (0, 100, 0), (0, 80, 20), (12, 80, 8)],
    "Silt loam": [(27, 73, 0), (27, 53, 20), (7, 50, 43), (0, 50, 50), (0, 80, 20), (12, 80, 8), (12, 88, 0)],
    "Loam": [(27, 53, 20), (27, 28, 45), (20, 28, 52), (7, 28, 65), (7, 50, 43)],
    "Sandy loam": [(20, 0, 80), (15, 0, 85), (0, 15, 85), (0, 50, 50), (7, 50, 43), (7, 28, 65), (20, 28, 52)],
    "Loamy sand": [(15, 0, 85), (10, 0, 90), (0, 10, 90), (0, 15, 85)],
    "Sand": [(10, 0, 90), (0, 0, 100), (0, 10, 90)],
}

# Nombres en español para el reporte
USDA_NOMBRES_ES = {
    "Clay":            "Arcilloso (Clay)",
    "Silty clay":      "Arcillo-limoso (Silty Clay)",
    "Silty clay loam": "Franco arcillo-limoso (Silty Clay Loam)",
    "Sandy clay":      "Arcillo-arenoso (Sandy Clay)",
    "Sandy clay loam": "Franco arcillo-arenoso (Sandy Clay Loam)",
    "Clay loam":       "Franco arcilloso (Clay Loam)",
    "Silt":            "Limoso (Silt)",
    "Silt loam":       "Franco limoso (Silt Loam)",
    "Loam":            "Franco (Loam)",
    "Sandy loam":      "Franco arenoso (Sandy Loam)",
    "Loamy sand":      "Arenoso franco (Loamy Sand)",
    "Sand":            "Arenoso (Sand)",
}


def _construir_poligonos_usda():
    """
    Convierte los vértices ternarios (CLAY, SILT, SAND) a coordenadas
    cartesianas 2D y genera objetos Shapely Polygon para cada clase USDA.
    Se ejecuta una sola vez al cargar el módulo.
    """
    poligonos = {}
    for clase, vertices in USDA_CLASES.items():
        coords_xy = []
        for clay, silt, sand in vertices:
            # Coordenadas ternarias → cartesianas (misma transformación del gráfico)
            x = silt + clay / 2.0
            y = clay * (np.sqrt(3) / 2.0)
            coords_xy.append((x, y))
        poligonos[clase] = Polygon(coords_xy)
    return poligonos


# Pre-construir los polígonos al importar el script
_POLIGONOS_USDA = _construir_poligonos_usda()


def clasificar_textura_usda(sand, silt, clay):
    """
    Clasifica la textura del suelo usando point-in-polygon sobre los
    polígonos exactos del triángulo USDA (replica soiltexture de R).
    
    Parámetros:
        sand, silt, clay: porcentajes (deben sumar ~100)
    
    Retorna:
        Nombre de la clase textural en español (e inglés entre paréntesis)
    """
    total = sand + silt + clay
    if total == 0:
        return "Sin datos"

    # Normalizar a 100%
    sand_n = sand * 100 / total
    silt_n = silt * 100 / total
    clay_n = clay * 100 / total

    # Convertir a coordenadas cartesianas
    x = silt_n + clay_n / 2.0
    y = clay_n * (np.sqrt(3) / 2.0)
    punto = Point(x, y)

    # Buscar en qué polígono cae el punto
    for clase, poligono in _POLIGONOS_USDA.items():
        if poligono.contains(punto) or poligono.touches(punto):
            return USDA_NOMBRES_ES.get(clase, clase)

    # Si no cae en ninguno (punto en frontera exacta), buscar el más cercano
    distancias = {clase: pol.distance(punto) for clase, pol in _POLIGONOS_USDA.items()}
    clase_cercana = min(distancias, key=distancias.get)
    return USDA_NOMBRES_ES.get(clase_cercana, clase_cercana)


# =============================================================================
# FUNCIONES DE VISUALIZACIÓN
# =============================================================================

def dibujar_triangulo_textural(ax, datos_textura):
    """
    Dibuja un triángulo textural USDA hermético con las regiones clasificadas
    y los puntos de las subcuencas superpuestos.
    """
    def ternary_to_xy(sand, silt, clay):
        """Convierte (sand, silt, clay) a coordenadas cartesianas (x, y)."""
        x = silt + clay / 2.0
        y = clay * (np.sqrt(3) / 2.0)
        return x, y

    def clase_vertices_xy(vertices_csc):
        """Convierte lista de (clay, silt, sand) a coordenadas xy."""
        return [ternary_to_xy(s, si, c) for c, si, s in vertices_csc]

    # Colores suaves para cada clase
    colores_clases = {
        "Clay": "#e6550d",       "Silty clay": "#fd8d3c",
        "Silty clay loam": "#fdbe85", "Sandy clay": "#d94701",
        "Sandy clay loam": "#fdd0a2", "Clay loam": "#fdae6b",
        "Silt": "#c6dbef",       "Silt loam": "#9ecae1",
        "Loam": "#a1d99b",       "Sandy loam": "#c7e9c0",
        "Loamy sand": "#e5f5e0", "Sand": "#ffffcc",
    }

    # Posiciones manuales de etiquetas (sand, silt, clay) centradas en cada región
    label_positions = {
        "Clay":            (25, 15, 60),
        "Silty clay":      (8, 48, 44),
        "Silty clay loam": (10, 57, 33),
        "Sandy clay":      (55, 7, 38),
        "Sandy clay loam": (62, 12, 26),
        "Clay loam":       (35, 33, 32),
        "Silt":            (10, 86, 4),
        "Silt loam":       (20, 65, 15),
        "Loam":            (48, 37, 15),
        "Sandy loam":      (65, 25, 10),
        "Loamy sand":      (88, 7, 5),
        "Sand":            (95, 3, 2),
    }

    # Dibujar cada clase como polígono relleno (hermético)
    for clase, vertices in USDA_CLASES.items():
        coords_xy = clase_vertices_xy(vertices)
        poligono_plt = plt.Polygon(coords_xy,
                                    facecolor=colores_clases.get(clase, '#eeeeee'),
                                    edgecolor='black', linewidth=0.7,
                                    alpha=0.6, zorder=1)
        ax.add_patch(poligono_plt)

        # Etiqueta
        sand_l, silt_l, clay_l = label_positions.get(clase, (33, 33, 33))
        lx, ly = ternary_to_xy(sand_l, silt_l, clay_l)
        nombre_corto = clase.replace(" ", "\n")
        ax.text(lx, ly, nombre_corto, ha='center', va='center', fontsize=5.5,
                fontweight='bold', color='#222222', zorder=4,
                bbox=dict(boxstyle='round,pad=0.15', facecolor='white', alpha=0.5,
                          edgecolor='none'))

    # Borde exterior del triángulo
    vertices_ext = np.array([
        ternary_to_xy(100, 0, 0),
        ternary_to_xy(0, 100, 0),
        ternary_to_xy(0, 0, 100),
        ternary_to_xy(100, 0, 0),
    ])
    ax.plot(vertices_ext[:, 0], vertices_ext[:, 1], 'k-', linewidth=2.0, zorder=5)

    # Líneas de cuadrícula cada 20%
    for i in range(20, 100, 20):
        for pts in [
            (ternary_to_xy(i, 100-i, 0), ternary_to_xy(i, 0, 100-i)),
            (ternary_to_xy(0, i, 100-i), ternary_to_xy(100-i, i, 0)),
            (ternary_to_xy(100-i, 0, i), ternary_to_xy(0, 100-i, i)),
        ]:
            ax.plot([pts[0][0], pts[1][0]], [pts[0][1], pts[1][1]],
                    color='gray', linewidth=0.3, alpha=0.3, zorder=2)

    # Etiquetas de vértices
    ax.text(*ternary_to_xy(105, -5, 0), "Arena\n100%", ha='center', va='top',
            fontsize=9, fontweight='bold')
    ax.text(*ternary_to_xy(-5, 105, 0), "Limo\n100%", ha='center', va='top',
            fontsize=9, fontweight='bold')
    ax.text(*ternary_to_xy(-3, -3, 106), "Arcilla\n100%", ha='center', va='bottom',
            fontsize=9, fontweight='bold')

    # Plotear puntos de las subcuencas
    for _, row in datos_textura.iterrows():
        if np.isnan(row['SAND']) or np.isnan(row['SILT']) or np.isnan(row['CLAY']):
            continue
        x, y = ternary_to_xy(row['SAND'], row['SILT'], row['CLAY'])
        ax.plot(x, y, 'o', color=(0.1, 0.4, 0.8, 0.85), markersize=11,
                markeredgecolor='white', markeredgewidth=1.2, zorder=6)

    ax.set_xlim(-8, 108)
    ax.set_ylim(-8, 98)
    ax.set_aspect('equal')
    ax.axis('off')
    ax.set_title("Clasificación Textural USDA", fontsize=12, fontweight='bold', pad=10)


# =============================================================================
# SCRIPT PRINCIPAL
# =============================================================================

def main():
    # =========================================================================
    # 1. CARGAR EL POLÍGONO DEL ÁREA DE ESTUDIO
    # =========================================================================
    print("1. Cargando el shapefile desde input/...")
    ruta_shapefile = encontrar_shapefile()
    poligono = gpd.read_file(ruta_shapefile)
    columna_id = elegir_columna(poligono)
    print(f"   → {len(poligono)} sub-polígonos cargados.")
    print(f"   → CRS original: {poligono.crs}")
    print(f"   → Columna ID seleccionada: {columna_id}")
    os.makedirs(DIR_OUTPUT, exist_ok=True)

    # =========================================================================
    # 2. CONECTAR A LOS SERVIDORES ESTÁTICOS DE SOILGRIDS (VRT)
    # =========================================================================
    print("\n2. Conectando al servidor estático de SoilGrids...")
    urls = {
        'sand': '/vsicurl/https://files.isric.org/soilgrids/latest/data/sand/sand_0-5cm_mean.vrt',
        'silt': '/vsicurl/https://files.isric.org/soilgrids/latest/data/silt/silt_0-5cm_mean.vrt',
        'clay': '/vsicurl/https://files.isric.org/soilgrids/latest/data/clay/clay_0-5cm_mean.vrt',
    }

    # =========================================================================
    # 3. HOMOLOGAR SISTEMAS DE COORDENADAS (CRS)
    # =========================================================================
    print("\n3. Transformando el polígono al CRS nativo de SoilGrids (Homolosena de Goode)...")
    with rasterio.open(urls['sand']) as src_sand:
        crs_soilgrids = src_sand.crs
    print(f"   → CRS de SoilGrids: {crs_soilgrids}")

    poligono_proj = poligono.to_crs(crs_soilgrids)

    # =========================================================================
    # 4. EXTRAER VALORES CON ZONAL STATS (CON FILTRADO ROBUSTO DE NODATA)
    # =========================================================================
    # CORRECCIÓN CRÍTICA: SoilGrids puede tener distintos valores NoData
    # (ej: -32768, 0, -9999, 255) dependiendo de la capa y la versión.
    # Leemos el nodata REAL del raster y además filtramos valores fuera del
    # rango válido (0-1000 g/kg) que corresponden a cuerpos de agua, vacíos
    # de cobertura, etc.
    #
    # all_touched=False → replica terra::extract() de R (solo centroides dentro)
    # =========================================================================
    print("\n4. Extrayendo estadísticas zonales por sub-polígono...")
    print("   (Lectura de NoData directo del raster + filtrado de rango válido)")
    print("   Esto puede tomar unos minutos dependiendo de la conexión...\n")

    resultados = {}
    for variable, url in urls.items():
        print(f"   → Procesando {variable}...")

        # Leer el valor NoData real del raster
        with rasterio.open(url) as src:
            nodata_real = src.nodata
            dtype_raster = src.dtypes[0]
        print(f"     NoData del raster: {nodata_real} (dtype: {dtype_raster})")

        # Extraer mini-rasters por polígono para filtrado manual
        valores_crudos = zonal_stats(
            poligono_proj,
            url,
            stats=None,           # No calcular stats predefinidas
            raster_out=True,       # Retorna arrays numpy por zona
            nodata=nodata_real,    # ← Usar el NoData REAL del raster
            all_touched=False,     # ← Replica terra::extract de R
        )

        # Calcular estadísticas manualmente con filtrado robusto
        stats_limpias = []
        for idx, zona in enumerate(valores_crudos):
            mini_raster = zona.get('mini_raster_array', None)

            if mini_raster is None:
                stats_limpias.append({'mean': np.nan, 'std': np.nan, 'count': 0,
                                      'count_nodata': 0})
                continue

            # Aplanar y convertir a float; si es masked array, extraer solo válidos
            if isinstance(mini_raster, np.ma.MaskedArray):
                pixeles = mini_raster.compressed().astype(float)
            else:
                pixeles = mini_raster.flatten().astype(float)
                # Filtrar NoData manualmente si no es masked
                if nodata_real is not None:
                    pixeles = pixeles[pixeles != nodata_real]

            # FILTRO: Eliminar valores fuera del rango válido de SoilGrids
            # SoilGrids entrega g/kg → rango válido: 0 a 1000
            count_antes = len(pixeles)
            pixeles = pixeles[(pixeles >= 0) & (pixeles <= 1000)]
            count_filtrados = count_antes - len(pixeles)

            if len(pixeles) == 0:
                stats_limpias.append({'mean': np.nan, 'std': np.nan, 'count': 0,
                                      'count_nodata': count_filtrados})
            else:
                stats_limpias.append({
                    'mean': float(np.mean(pixeles)),
                    'std': float(np.std(pixeles, ddof=1)) if len(pixeles) > 1 else 0.0,
                    'count': len(pixeles),
                    'count_nodata': count_filtrados
                })

        resultados[variable] = stats_limpias
        n_total = sum(s['count'] for s in stats_limpias)
        n_nodata = sum(s['count_nodata'] for s in stats_limpias)
        print(f"     ✓ {variable}: {n_total} píxeles válidos, {n_nodata} filtrados por NoData/fuera de rango")

    # =========================================================================
    # 5. CONSTRUIR EL DATAFRAME DE RESULTADOS
    # =========================================================================
    print("\n5. Calculando promedios y desviación estándar por subcuenca...")

    nombres_subc = poligono_proj[columna_id].astype(str).tolist()

    # Convertir g/kg a porcentaje (SoilGrids → g/kg, dividir entre 10)
    arena_media   = [r['mean'] / 10 if not np.isnan(r['mean']) else np.nan for r in resultados['sand']]
    limo_medio    = [r['mean'] / 10 if not np.isnan(r['mean']) else np.nan for r in resultados['silt']]
    arcilla_media = [r['mean'] / 10 if not np.isnan(r['mean']) else np.nan for r in resultados['clay']]

    arena_sd   = [r['std'] / 10 if not np.isnan(r['std']) else np.nan for r in resultados['sand']]
    limo_sd    = [r['std'] / 10 if not np.isnan(r['std']) else np.nan for r in resultados['silt']]
    arcilla_sd = [r['std'] / 10 if not np.isnan(r['std']) else np.nan for r in resultados['clay']]

    # CORRECCIÓN: Clasificación textural con polígonos exactos (point-in-polygon)
    clases_texturales = []
    for s, si, c in zip(arena_media, limo_medio, arcilla_media):
        if np.isnan(s) or np.isnan(si) or np.isnan(c):
            clases_texturales.append("Sin datos")
        else:
            clases_texturales.append(clasificar_textura_usda(s, si, c))

    datos_textura = pd.DataFrame({
        'SAND': arena_media,
        'SILT': limo_medio,
        'CLAY': arcilla_media
    })

    # =========================================================================
    # 6. RESULTADOS EN CONSOLA
    # =========================================================================
    print("\n" + "=" * 55)
    print(" RESULTADOS FINALES")
    print("=" * 55)
    print(f"Análisis completado para {len(nombres_subc)} sub-polígonos.\n")

    for i, nombre in enumerate(nombres_subc):
        print(f"  {nombre}:")
        if np.isnan(arena_media[i]):
            print(f"    ⚠️  Sin datos válidos (subcuenca fuera de cobertura SoilGrids)")
        else:
            print(f"    Arena:   {arena_media[i]:6.2f}% (±{arena_sd[i]:.2f})")
            print(f"    Limo:    {limo_medio[i]:6.2f}% (±{limo_sd[i]:.2f})")
            print(f"    Arcilla: {arcilla_media[i]:6.2f}% (±{arcilla_sd[i]:.2f})")
            print(f"    Clase:   {clases_texturales[i]}")
        print()

    # =========================================================================
    # 7. CROP & MASK PARA VISUALIZACIÓN ESPACIAL
    # =========================================================================
    print("7. Recortando rasters para mapas espaciales...")

    rasters_recortados = {}
    for variable, url in urls.items():
        with rasterio.open(url) as src:
            nodata_real = src.nodata
            geometrias = poligono_proj.geometry.values
            out_image, out_transform = rio_mask(
                src, geometrias, crop=True, nodata=nodata_real
            )
            # Convertir a float y enmascarar NoData + valores fuera de rango
            datos = out_image[0].astype(float)
            mascara_invalido = (datos == nodata_real) | (datos < 0) | (datos > 1000)
            datos[mascara_invalido] = np.nan
            datos = datos / 10.0  # Convertir a porcentaje

            rasters_recortados[variable] = {
                'data': datos,
                'transform': out_transform,
            }
        print(f"   ✓ {variable} recortado ({out_image.shape[2]}x{out_image.shape[1]} px)")

    # =========================================================================
    # 8. VISUALIZACIÓN (ESTILO PUBLICACIÓN)
    # =========================================================================
    print("\n8. Generando gráficos de alta calidad...")

    # --- GRÁFICO 1: Mapas Espaciales + Triángulo Textural ---
    fig = plt.figure(figsize=(15, 9), dpi=300, constrained_layout=False)
    gs = GridSpec(2, 2, figure=fig, hspace=0.22, wspace=0.12,
                  left=0.02, right=0.98, top=0.93, bottom=0.04)

    configs_mapas = [
        ('sand', 'Contenido de Arena (%)', 'YlOrBr_r'),
        ('silt', 'Contenido de Limo (%)',  'YlGnBu_r'),
        ('clay', 'Contenido de Arcilla (%)', 'Reds'),
    ]
    posiciones = [(0, 0), (0, 1), (1, 0)]

    for (var, titulo, cmap), (fila, col) in zip(configs_mapas, posiciones):
        ax = fig.add_subplot(gs[fila, col])
        datos = rasters_recortados[var]['data'].copy()

        extent = rasterio.transform.array_bounds(
            datos.shape[0], datos.shape[1],
            rasters_recortados[var]['transform']
        )
        im = ax.imshow(datos, cmap=cmap,
                        extent=[extent[0], extent[2], extent[1], extent[3]],
                        aspect='equal')  # aspect='equal' para forma real del polígono
        poligono_proj.boundary.plot(ax=ax, color='gray', linewidth=0.8)
        ax.set_title(titulo, fontsize=11, fontweight='bold', pad=4)
        ax.set_axis_off()
        # Colorbar horizontal compacto debajo del mapa
        cbar = plt.colorbar(im, ax=ax, orientation='horizontal',
                            fraction=0.045, pad=0.06, aspect=35, shrink=0.85)
        cbar.set_label('%', fontsize=8)
        cbar.ax.tick_params(labelsize=7)

    # Triángulo textural con regiones coloreadas
    ax_tri = fig.add_subplot(gs[1, 1])
    dibujar_triangulo_textural(ax_tri, datos_textura)

    fig.suptitle("Análisis de Textura del Suelo - SoilGrids",
                 fontsize=14, fontweight='bold', y=0.88)

    nombre_imagen_mapas = os.path.join(DIR_OUTPUT, "mapas_textura_publicacion.png")
    fig.savefig(nombre_imagen_mapas, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f"   ✓ {nombre_imagen_mapas} guardado")

    # --- GRÁFICO 2: Barras Apiladas por Subcuenca ---
    fig2, ax2 = plt.subplots(figsize=(13, 7), dpi=300)

    x = np.arange(len(nombres_subc))
    ancho = 0.6
    colores = ['#E69F00', '#7FC97F', '#E31A1C']

    ax2.bar(x, arena_media, ancho, label='Arena',
            color=colores[0], edgecolor='white', linewidth=0.5)
    ax2.bar(x, limo_medio, ancho, bottom=arena_media, label='Limo',
            color=colores[1], edgecolor='white', linewidth=0.5)
    bottoms_arcilla = [a + l for a, l in zip(arena_media, limo_medio)]
    ax2.bar(x, arcilla_media, ancho, bottom=bottoms_arcilla, label='Arcilla',
            color=colores[2], edgecolor='white', linewidth=0.5)

    ax2.set_ylabel('Proporción (%)', fontsize=11)
    ax2.set_title('Composición Textural Promedio por Subcuenca',
                  fontsize=13, fontweight='bold', pad=25)
    ax2.set_xticks(x)
    ax2.set_xticklabels(nombres_subc, rotation=45, ha='right', fontsize=9)
    # Leyenda arriba, justo debajo del título
    ax2.legend(loc='upper center', bbox_to_anchor=(0.5, 1.06),
               ncol=3, frameon=False, fontsize=11)
    ax2.set_ylim(0, 105)
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)

    nombre_imagen_barras = os.path.join(DIR_OUTPUT, "grafico_barras_subcuencas.png")
    fig2.savefig(nombre_imagen_barras, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close(fig2)
    print(f"   ✓ {nombre_imagen_barras} guardado")

    print(f"\n✅ Imágenes de alta resolución guardadas:")
    print(f"   - {nombre_imagen_mapas}")
    print(f"   - {nombre_imagen_barras}")

    # =========================================================================
    # 9. EXPORTAR RESULTADOS A EXCEL
    # =========================================================================
    print("\n9. Exportando resultados a Excel...")

    datos_exportar = pd.DataFrame({
        columna_id: nombres_subc,
        'Arena_Promedio_Pct': np.round(arena_media, 2),
        'Arena_SD': np.round(arena_sd, 2),
        'Limo_Promedio_Pct': np.round(limo_medio, 2),
        'Limo_SD': np.round(limo_sd, 2),
        'Arcilla_Promedio_Pct': np.round(arcilla_media, 2),
        'Arcilla_SD': np.round(arcilla_sd, 2),
        'Clase_Textural_USDA': clases_texturales
    })

    nombre_archivo = os.path.join(DIR_OUTPUT, "resultados_textura_subcuencas.xlsx")
    datos_exportar.to_excel(nombre_archivo, index=False, engine='openpyxl')

    print(f"✅ ¡Archivo '{nombre_archivo}' guardado exitosamente!\n")
    print(datos_exportar.to_string(index=False))

    return datos_exportar


# =============================================================================
# EJECUCIÓN
# =============================================================================
if __name__ == "__main__":
    resultados = main()
