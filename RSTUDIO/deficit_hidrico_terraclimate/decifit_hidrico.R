# ==============================================================================
# SCRIPT PARA ANÁLISIS AGROCLIMÁTICO: DÉFICIT HÍDRICO (TERRACLIMATE)
#
# Convenciones del proyecto:
#   - input/   (tú creas esta carpeta y pones ahí el shapefile)
#   - output/  (se crea automáticamente al ejecutar; aquí van los resultados)
#
# Configuración:
#   - COL_ID: nombre de la columna del shapefile que identifica cada polígono.
#     Si lo dejas en NULL, el script intenta detectarla automáticamente
#     buscando nombres comunes (nombre, name, id, ...). Si hay varios
#     shapefiles o columnas candidatas, se usa la primera.
# ==============================================================================

# Instalar paquetes si es necesario
# install.packages(c("sf", "terra", "writexl"))

library(sf)
library(terra)
library(writexl)

# ------------------------------------------------------------------------------
# Configuración
# ------------------------------------------------------------------------------
# COL_ID: nombre de la columna del shapefile que identifica cada polígono.
#   - NULL   -> el script te preguntará en un diálogo (RStudio) o por consola,
#               mostrando las columnas disponibles antes de preguntar.
#   - "xxx"  -> usa esa columna directamente (si existe).
COL_ID <- NULL

# ------------------------------------------------------------------------------
# Utilidades
# ------------------------------------------------------------------------------
encontrar_shapefile <- function(dir_input = "input") {
  if (!dir.exists(dir_input)) {
    stop(sprintf("No existe la carpeta '%s/'. Créala y coloca ahí tu shapefile (.shp + .shx + .dbf + .prj).", dir_input))
  }
  shps <- list.files(dir_input, pattern = "\\.shp$", full.names = TRUE, recursive = TRUE)
  if (length(shps) == 0) {
    stop(sprintf("No se encontró ningún .shp dentro de '%s/'.", dir_input))
  }
  if (length(shps) > 1) {
    cat("Se encontraron varios shapefiles en input/. Se usará el primero:\n")
    for (i in seq_along(shps)) cat(sprintf("  %d. %s\n", i, shps[i]))
  }
  cat(sprintf("[OK] Shapefile detectado: %s\n", shps[1]))
  shps[1]
}

preguntar <- function(mensaje, default = "") {
  # Usa diálogo de RStudio si está disponible (funciona con Source).
  # Si no, cae a readline() (funciona ejecutando línea a línea con Ctrl+Enter).
  if (requireNamespace("rstudioapi", quietly = TRUE) && rstudioapi::isAvailable()) {
    resp <- rstudioapi::showPrompt(title = "Columna identificadora",
                                   message = mensaje, default = default)
    if (is.null(resp)) stop("Operación cancelada por el usuario.")
    return(trimws(resp))
  }
  trimws(readline(paste0(mensaje, " ")))
}

elegir_columna <- function(sf_obj, col_id = NULL) {
  cols <- setdiff(names(sf_obj), attr(sf_obj, "sf_column"))
  if (length(cols) == 0) {
    stop("El shapefile no tiene columnas de atributos.")
  }
  if (!is.null(col_id) && nzchar(col_id) && col_id %in% cols) {
    cat(sprintf("[OK] Columna ID (configurada): %s\n", col_id))
    return(col_id)
  }
  # Mostrar columnas y ejemplos en la consola antes de preguntar
  cat("\nColumnas disponibles en el shapefile:\n")
  for (i in seq_along(cols)) {
    ejem <- paste(head(as.character(sf_obj[[cols[i]]]), 3), collapse = ", ")
    cat(sprintf("  %2d. %-20s -> ejemplos: %s\n", i, cols[i], ejem))
  }
  msg <- sprintf("¿Qué columna identifica cada polígono?\nEscribe el nombre o el número.\nColumnas: %s",
                 paste(cols, collapse = ", "))
  repeat {
    resp <- preguntar(msg, default = cols[1])
    if (nchar(resp) == 0) { cat("Vacío. Intenta de nuevo.\n"); next }
    if (grepl("^[0-9]+$", resp)) {
      idx <- as.integer(resp)
      if (idx >= 1 && idx <= length(cols)) {
        cat(sprintf("[OK] Columna ID seleccionada: %s\n", cols[idx]))
        return(cols[idx])
      }
    } else if (resp %in% cols) {
      cat(sprintf("[OK] Columna ID seleccionada: %s\n", resp))
      return(resp)
    }
    cat(sprintf("Entrada inválida: '%s'. Intenta de nuevo.\n", resp))
  }
}

# ------------------------------------------------------------------------------
# 1. Cargar el polígono de área de estudio
# ------------------------------------------------------------------------------
cat("1. Cargando el shapefile desde input/...\n")
ruta_shp <- encontrar_shapefile("input")
poligono <- st_read(ruta_shp, quiet = TRUE)
col_id <- elegir_columna(poligono, COL_ID)

poligono_vect <- vect(poligono)
poligono_wgs84 <- project(poligono_vect, "EPSG:4326")
nombres_subc <- as.character(poligono_wgs84[[col_id]][[1]])

# Asegurar carpeta de salida
dir.create("output", showWarnings = FALSE, recursive = TRUE)

# ------------------------------------------------------------------------------
# 2. Descargar datos de TerraClimate (déficit hídrico, año 2024)
# ------------------------------------------------------------------------------
cat("2. Descargando datos climáticos de TerraClimate (déficit, año 2024)...\n")
url_terraclimate <- "http://thredds.northwestknowledge.net:8080/thredds/fileServer/TERRACLIMATE_ALL/data/TerraClimate_def_2024.nc"
temp_nc <- tempfile(fileext = ".nc")
options(timeout = 300)
download.file(url_terraclimate, destfile = temp_nc, mode = "wb", quiet = TRUE)
r_def_reciente <- rast(temp_nc)

# ------------------------------------------------------------------------------
# 3. Preparar capas mensuales
# ------------------------------------------------------------------------------
cat("3. Preparando capas mensuales...\n")
nombres_meses <- c("Ene", "Feb", "Mar", "Abr", "May", "Jun",
                   "Jul", "Ago", "Sep", "Oct", "Nov", "Dic")
names(r_def_reciente) <- nombres_meses

# ------------------------------------------------------------------------------
# 4. Recorte espacial con suavizado bilineal
# ------------------------------------------------------------------------------
cat("4. Recortando y suavizando los datos al polígono...\n")
def_crop  <- crop(r_def_reciente, poligono_wgs84)
def_suave <- disagg(def_crop, fact = 20, method = "bilinear")
def_mask  <- mask(def_suave, poligono_wgs84)
def_anual <- sum(def_mask, na.rm = TRUE)

# ------------------------------------------------------------------------------
# 5. Estadísticas por polígono
# ------------------------------------------------------------------------------
cat("5. Calculando el déficit mensual por polígono...\n")
extraccion_mensual <- terra::extract(def_mask, poligono_wgs84, fun = mean, na.rm = TRUE)
tabla_mensual <- round(extraccion_mensual[, -1], 1)
tabla_final   <- cbind(Poligono = nombres_subc, tabla_mensual)
tabla_final$Total_Anual_mm <- rowSums(tabla_mensual)
names(tabla_final)[1] <- col_id  # respeta el nombre de la columna elegida

# ------------------------------------------------------------------------------
# 6. Gráficos (todos se guardan en output/)
# ------------------------------------------------------------------------------
cat("6. Generando gráficos (300 DPI)...\n")

dibujar_mapa <- function() {
  par(mar = c(2, 2, 4, 6), family = "sans")
  pal_sequia <- hcl.colors(100, "YlOrRd", rev = TRUE)
  plot(def_anual, main = "Déficit Hídrico Acumulado Anual (mm/año)",
       col = pal_sequia, axes = FALSE, box = FALSE,
       plg = list(title = " mm", cex = 0.9))
  plot(poligono_wgs84, add = TRUE, border = "gray20", lwd = 1.5)
}

dibujar_barras <- function() {
  par(mar = c(4, 5, 4, 2), family = "sans")
  promedio_regional_mensual <- colMeans(tabla_mensual)
  pos_barras <- barplot(promedio_regional_mensual,
                        main = "Evolución Mensual del Déficit Hídrico (Promedio Regional)",
                        ylab = "Déficit Hídrico (mm/mes)",
                        col = "coral", border = "darkred",
                        ylim = c(0, max(promedio_regional_mensual) * 1.2),
                        las = 1, cex.names = 0.9)
  text(x = pos_barras,
       y = promedio_regional_mensual + (max(promedio_regional_mensual) * 0.05),
       labels = round(promedio_regional_mensual, 0), cex = 0.8)
  lines(x = pos_barras, y = promedio_regional_mensual,
        col = "darkred", lwd = 2, lty = 2)
  points(x = pos_barras, y = promedio_regional_mensual,
         col = "darkred", pch = 19)
}

out_mapa   <- file.path("output", "mapa_deficit_hidrico.png")
out_barras <- file.path("output", "barras_deficit_hidrico.png")
out_excel  <- file.path("output", "resultados_deficit_hidrico_mensual.xlsx")

png(out_mapa, width = 2800, height = 1600, res = 300); dibujar_mapa(); invisible(dev.off())
png(out_barras, width = 2400, height = 1600, res = 300); dibujar_barras(); invisible(dev.off())

# Mostrar en RStudio
dibujar_mapa()
dibujar_barras()

# ------------------------------------------------------------------------------
# 7. Exportar a Excel
# ------------------------------------------------------------------------------
cat("7. Exportando resultados a Excel...\n")
write_xlsx(tabla_final, path = out_excel)

unlink(temp_nc)

cat("\n====================================================\n")
cat("PROCESO COMPLETADO\n")
cat("Archivos generados en output/:\n")
cat("  1. Mapa:  ", out_mapa,   "\n")
cat("  2. Barras:", out_barras, "\n")
cat("  3. Excel: ", out_excel,  "\n")
cat("====================================================\n")
