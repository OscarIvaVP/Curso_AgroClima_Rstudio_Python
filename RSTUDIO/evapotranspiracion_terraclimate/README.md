# Análisis Agroclimático: Evapotranspiración Real (AET - TerraClimate)

Script en R diseñado para extraer y analizar la Evapotranspiración Real (AET) mensual y anual, facilitando el balance hídrico en áreas de estudio agrícolas o hidrológicas.

## Detalle de la Fuente de Información (TerraClimate)
**TerraClimate** proporciona variables climáticas y de balance hídrico superficial mediante un modelo de balance hídrico de un solo nivel.

*   **Institución:** Climatology Lab de la Universidad de California, Merced.
*   **Resolución Espacial:** 1/24° (~4 km x 4 km).
*   **Cobertura Geográfica:** Global (superficies terrestres).
*   **Naturaleza del Dato:** Utiliza un modelo de balance hídrico de Thorne-Thwaite que incorpora datos de temperatura, precipitación y capacidad de almacenamiento de agua del suelo.
*   **Variable Procesada:** `aet` (Actual Evapotranspiration). Representa la cantidad de agua que efectivamente se evapora del suelo y es transpirada por la vegetación.
*   **Serie Histórica:** Desde 1958 hasta el presente.
*   **Unidades:** Milímetros (mm/mes).

## Funcionalidad
- **Conexión THREDDS**: Descarga directa de datos NetCDF para el año 2023.
- **Suavizado Espacial**: Aplica interpolación bilineal para mejorar la resolución visual y analítica sobre los polígonos de interés.
- **Análisis por Polígono**: Extrae estadísticas medias mensuales para cada entidad geográfica definida por el usuario.
- **Reportes Visuales**:
  - Mapa de AET acumulada anual.
  - Paneles con la evolución de los 12 mapas mensuales.
  - Gráfico de barras de la tendencia regional.
- **Exportación**: Resultados tabulares listos para análisis en Excel.

## Cómo se usa
1.  **Entrada**: Asegúrate de que el Shapefile esté en la carpeta `input/`.
2.  **Dependencias**: Requiere los paquetes `sf`, `terra` y `writexl`.
3.  **Ejecución**: Ejecuta `evapotransporacion.R` desde R o RStudio.
4.  **Interacción**: Sigue las instrucciones en consola o diálogos para seleccionar la columna de identificación (ID).
5.  **Salida**: Revisa la carpeta `output/` para los gráficos y el archivo Excel.
