# Análisis Agroclimático: Precipitación Mensual (CHIRPS v2.0)

Este script automatiza la descarga y el procesamiento de datos de precipitación global de alta resolución provenientes de CHIRPS. Está diseñado para calcular estadísticas zonales precisas sobre polígonos de interés y generar reportes visuales listos para publicación.

## Detalle de la Fuente de Información (CHIRPS v2.0)
El conjunto de datos **CHIRPS** (Climate Hazards Group InfraRed Precipitation with Station data) es un producto cuasi-global diseñado específicamente para el monitoreo de sequías y la planificación agrícola.

*   **Institución:** Climate Hazards Center de la Universidad de California, Santa Barbara (UCSB).
*   **Resolución Espacial:** 0.05° (~5.3 km x 5.3 km en el ecuador).
*   **Cobertura Geográfica:** Global, limitada a las latitudes 50°S a 50°N.
*   **Naturaleza del Dato:** Es un producto "mezclado" (blended) que combina estimaciones satelitales infrarrojas (nubosidad y temperatura de tope de nube) con datos de estaciones meteorológicas terrestres.
*   **Serie Histórica:** Disponible desde 1981 hasta el presente.
*   **Unidades:** El script procesa el acumulado mensual en milímetros (mm/mes).

## Funcionalidad
- **Descarga Automática**: Obtiene GeoTIFFs mensuales directamente de los servidores de la UCSB para un año específico.
- **Procesamiento Espacial**: Realiza un remuestreo bilineal (factor x20) para mejorar la precisión en polígonos pequeños y mitigar el efecto de borde.
- **Estadísticas Zonales**: Calcula el promedio regional mensual y el acumulado anual por cada polígono detectado en el Shapefile.
- **Visualización**: Genera mapas de calor de alta resolución (anual y serie de 12 meses) y gráficos de barras de la serie temporal.

## Cómo se usa
1.  **Entrada**: Coloca tu Shapefile en la carpeta `input/`.
2.  **Dependencias**: Instala las librerías necesarias: `pip install geopandas rasterio rasterstats matplotlib numpy pandas openpyxl`.
3.  **Ejecución**: Ejecuta `python precipitacion_chirps.py`.
4.  **Interacción**: Selecciona el archivo y la columna identificadora cuando el script lo solicite.
5.  **Salida**: Los resultados (mapas y Excel) se guardarán automáticamente en la carpeta `output/`.
