# Procesamiento de Temperatura Media (ERA5-Land)

Herramienta interactiva para la extracción y análisis de series históricas de temperatura superficial utilizando el reanálisis global ERA5-Land.

## Detalle de la Fuente de Información (ERA5-Land)
**ERA5-Land** es un reanálisis climático de quinta generación que ofrece una descripción detallada del clima terrestre de las últimas décadas con una consistencia física rigurosa.

*   **Institución:** Centro Europeo de Previsiones Meteorológicas a Plazo Medio (ECMWF) a través del Servicio de Cambio Climático de Copernicus (C3S).
*   **Resolución Espacial:** 0.1° (~9 km x 9 km).
*   **Cobertura Geográfica:** Global (áreas terrestres).
*   **Naturaleza del Dato:** Es un **Reanálisis**, lo que significa que utiliza un modelo atmosférico avanzado para integrar observaciones de satélites, globos sonda y estaciones, asegurando que los datos sean coherentes incluso donde no hay estaciones físicas.
*   **Variable:** `2m temperature` (temperatura del aire a 2 metros de altura).
*   **Serie Histórica:** Desde 1950 hasta el presente.
*   **Unidades:** El dato original en Kelvin (K) es convertido automáticamente por el script a Grados Celsius (°C).

## Funcionalidad
- **Acceso Directo**: Descarga automática de archivos GRIB mensuales desde el Copernicus Climate Data Store (CDS).
- **Análisis Multi-temporal**: Genera estadísticas mensuales, anuales y de amplitud térmica (máximos y mínimos).
- **Reportes Visuales**: Crea mapas coropléticos de temperatura media, series temporales de largo plazo y diagramas de caja (boxplots) para analizar la variabilidad.
- **Exportación**: Genera un archivo Excel multihonja con todos los procesamientos numéricos.

## Cómo se usa
1.  **Credenciales CDS**: Debes registrarte en [Copernicus CDS](https://cds.climate.copernicus.eu/) y configurar tu API Key.
2.  **Entrada**: Coloca tu Shapefile en la carpeta `input/`.
3.  **Ejecución**: Ejecuta `python temperatura_media.py`.
4.  **Interacción**: El script te guiará para elegir el archivo, el ID del polígono y el rango de años de interés.
5.  **Salida**: Los archivos finales se ubicarán en `output/`. Los datos crudos descargados se conservan en `output/datos/` como caché.
