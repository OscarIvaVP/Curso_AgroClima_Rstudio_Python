# Análisis de Textura del Suelo por Subcuenca (SoilGrids)

Este script en R utiliza la infraestructura de SoilGrids para determinar las fracciones granulométricas del suelo y clasificar la textura según el sistema USDA.

## Detalle de la Fuente de Información (SoilGrids 2.0)
**SoilGrids** es una base de datos global de propiedades del suelo que utiliza técnicas de mapeo digital basadas en aprendizaje automático.

*   **Institución:** ISRIC - World Soil Information.
*   **Resolución Espacial:** 250 metros.
*   **Cobertura Geográfica:** Global.
*   **Naturaleza del Dato:** Los mapas son predicciones generadas a partir de una vasta base de datos de perfiles de suelo y múltiples covariables ambientales.
*   **Profundidad**: Capa de **0-5 cm** (superficial).
*   **Variables Extraídas**:
    - **Sand (Arena):** % de partículas entre 0.05 y 2.0 mm.
    - **Silt (Limo):** % de partículas entre 0.002 y 0.05 mm.
    - **Clay (Arcilla):** % de partículas menores a 0.002 mm.
*   **Unidades**: El script convierte los valores originales de g/kg a porcentaje (%).

## Funcionalidad
- **Acceso Remoto (VRT)**: Consulta los datos directamente desde el servidor de ISRIC mediante el sistema de archivos virtual `/vsicurl/` de GDAL, optimizando el tiempo de procesamiento.
- **Clasificación USDA**: Integra el paquete `soiltexture` de R para una clasificación precisa basada en los promedios de arena, limo y arcilla.
- **Análisis Espacial**: Reproyecta automáticamente el área de estudio al CRS nativo de SoilGrids (Goode Homolosine) para una extracción sin distorsiones.
- **Visualización**:
  - Mapas de cada fracción granulométrica.
  - Triángulo textural USDA con la ubicación de las muestras.
  - Gráfico de barras de composición porcentual por polígono.

## Cómo se usa
1.  **Entrada**: Coloca el Shapefile en `input/`.
2.  **Dependencias**: Instala `sf`, `terra`, `soiltexture` y `writexl`.
3.  **Ejecución**: Ejecuta `textura_suelo.R`.
4.  **Salida**: Carpeta `output/` con mapas en alta resolución y tabla de Excel con el desglose textural.
