# Análisis de Textura del Suelo vía SoilGrids (VRT)

Este script determina la composición física del suelo (Arena, Limo y Arcilla) y su clasificación textural según el estándar USDA, consultando los servidores globales de SoilGrids de forma remota y eficiente.

## Detalle de la Fuente de Información (SoilGrids 2.0)
**SoilGrids** es un sistema de mapeo global de propiedades del suelo basado en modelos de aprendizaje automático (Machine Learning).

*   **Institución:** ISRIC - World Soil Information (Países Bajos).
*   **Resolución Espacial:** 250 metros.
*   **Cobertura Geográfica:** Global.
*   **Naturaleza del Dato:** Es un **Mapa Predictivo**. Se genera mediante modelos que correlacionan más de 240,000 perfiles de suelo reales con covariables ambientales (clima, relieve, vegetación).
*   **Profundidad:** El script consulta la capa superficial de **0-5 cm**.
*   **Variables:**
    - **Sand (Arena):** Partículas 0.05 a 2.0 mm.
    - **Silt (Limo):** Partículas 0.002 a 0.05 mm.
    - **Clay (Arcilla):** Partículas < 0.002 mm.
*   **Unidades:** Los datos se obtienen en g/kg y el script los convierte a porcentaje (%).

## Funcionalidad
- **Consulta VRT**: Utiliza Vistas Ráster Virtuales para leer solo los píxeles necesarios del servidor remoto, evitando descargas masivas.
- **Clasificación USDA**: Implementa una lógica de clasificación por polígonos exactos sobre el triángulo textural (point-in-polygon), asegurando resultados idénticos a los estándares científicos.
- **Filtrado de Calidad**: Elimina automáticamente valores fuera de rango o NoData correspondientes a cuerpos de agua o zonas sin suelo.
- **Gráficos Estilo Publicación**: Genera mapas espaciales, el triángulo textural USDA con muestras y diagramas de barras comparativos.

## Cómo se usa
1.  **Entrada**: Coloca tu Shapefile en la carpeta `input/`.
2.  **Ejecución**: Ejecuta `python textura_suelo_soilgrids.py`.
3.  **Interacción**: El script solicitará elegir el archivo y la columna que identifica a cada área (subcuenca, finca, etc.).
4.  **Salida**: 
    - `resultados_textura_subcuencas.xlsx`: Tabla con promedios y clase textural.
    - `mapas_textura_publicacion.png`: Composición espacial y triángulo textural.
    - `grafico_barras_subcuencas.png`: Comparativa visual de proporciones.
