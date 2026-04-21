# Análisis Agroclimático: Déficit Hídrico (TerraClimate)

Este script en R permite calcular y visualizar el déficit hídrico mensual y anual para un área de estudio específica, utilizando datos climáticos globales de alta resolución.

## Detalle de la Fuente de Información (TerraClimate)
**TerraClimate** es un conjunto de datos climáticos mensuales de alta resolución para superficies terrestres globales.

*   **Institución:** Climatology Lab de la Universidad de California, Merced.
*   **Resolución Espacial:** 1/24° (~4 km x 4 km).
*   **Cobertura Geográfica:** Global (superficies terrestres).
*   **Naturaleza del Dato:** Combina datos climáticos mensuales de alta resolución espacial de la serie WorldClim con datos de mayor resolución temporal de CRU Ts4.0 y el reanálisis JRA-55.
*   **Variable Procesada:** `def` (Water Deficit). El déficit hídrico es la diferencia entre la evapotranspiración potencial y la evapotranspiración real. Es un indicador clave de la demanda de agua no satisfecha por la humedad disponible en el suelo.
*   **Serie Histórica:** Desde 1958 hasta el presente (actualizado anualmente).
*   **Unidades:** El script procesa el acumulado mensual en milímetros (mm/mes).

## Funcionalidad
- **Descarga Automatizada**: Obtiene archivos NetCDF (.nc) directamente desde el servidor THREDDS para el año 2024.
- **Procesamiento Espacial**: 
  - Realiza un remuestreo bilineal (disagg factor 20) para suavizar los datos y adaptarlos mejor a geometrías locales.
  - Recorta y enmascara los datos según el Shapefile de entrada.
- **Estadísticas Zonales**: Calcula el promedio mensual de déficit hídrico por cada polígono individual en el Shapefile.
- **Visualización**: Genera un mapa de calor del acumulado anual y un gráfico de barras de la evolución mensual regional.
- **Exportación**: Genera un reporte detallado en Excel con los valores por polígono y totales anuales.

## Cómo se usa
1.  **Entrada**: Coloca tu Shapefile en la carpeta `input/`.
2.  **Dependencias**: Asegúrate de tener instalados los paquetes `sf`, `terra` y `writexl`.
3.  **Ejecución**: Abre `decifit_hidrico.R` en RStudio y ejecútalo.
4.  **Interacción**: El script detectará el Shapefile y te pedirá elegir la columna que identifica a los polígonos mediante un diálogo interactivo.
5.  **Salida**: Los archivos finales (mapas y Excel) se guardarán en la carpeta `output/`.
