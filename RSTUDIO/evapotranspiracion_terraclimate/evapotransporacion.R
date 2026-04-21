# ==============================================================================
# SCRIPT PARA ANÁLISIS AGROCLIMÁTICO: EVAPOTRANSPIRACIÓN REAL (AET - TERRACLIMATE)
#
# Convenciones del proyecto:
#   - input/   (tú creas esta carpeta y pones ahí el shapefile)
#   - output/  (se crea automáticamente al ejecutar; aquí van los resultados)
#
# Configuración:
#   - COL_ID: nombre de la columna que identifica cada polígono.
#       NULL  -> el script te preguntará con un diálogo (RStudio).
#       "xxx" -> usa esa columna directamente si existe.
# ==============================================================================

# install.packages(c("sf", "terra", "writexl"))

library(sf)
library(terra)
library(writexl)

# ------------------------------------------------------------------------------
# Configuración
# ------------------------------------------------------------------------------
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
  if (length(cols) == 0) stop("El shapefile no tiene columnas de atributos.")
  if (!is.null(col_id) && nzchar(col_id) && col_id %in% cols) {
    cat(sprintf("[OK] Columna ID (configurada): %s\n", col_id))
    return(col_id)
  }
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
# 1. Cargar shapefile
# ------------------------------------------------------------------------------
cat("1. Cargando el shapefile desde input/...\n")
ruta_shp <- encontrar_shapefile("input")
poligono <- st_read(ruta_shp, quiet = TRUE)
col_id <- elegir_columna(poligono, COL_ID)

poligono_vect  <- vect(poligono)
poligono_wgs84 <- project(poligono_vect, "EPSG:4326")
nombres_subc   <- as.character(poligono_wgs84[[col_id]][[1]])

dir.create("output", showWarnings = FALSE, recursive = TRUE)

# ------------------------------------------------------------------------------
# 2. Descargar TerraClimate (AET, año 2023)
# ------------------------------------------------------------------------------
cat("2. Descargando TerraClimate AET (año 2023)...\n")
url_terraclimate <- "http://thredds.northwestknowledge.net:8080/thredds/fileServer/TERRACLIMATE_ALL/data/TerraClimate_aet_2023.nc"
temp_nc <- tempfile(fileext = ".nc")
options(timeout = 300)
download.file(url_terraclimate, destfile = temp_nc, mode = "wb", quiet = TRUE)
r_aet_reciente <- rast(temp_nc)

# ------------------------------------------------------------------------------
# 3. Preparar capas mensuales
# ------------------------------------------------------------------------------
cat("3. Preparando capas mensuales...\n")
nombres_meses <- c("Ene", "Feb", "Mar", "Abr", "May", "Jun",
                   "Jul", "Ago", "Sep", "Oct", "Nov", "Dic")
names(r_aet_reciente) <- nombres_meses

# ------------------------------------------------------------------------------
# 4. Recorte espacial con suavizado bilineal
# ------------------------------------------------------------------------------
cat("4. Recortando y suavizando al polígono...\n")
aet_crop  <- crop(r_aet_reciente, poligono_wgs84)
aet_suave <- disagg(aet_crop, fact = 20, method = "bilinear")
aet_mask  <- mask(aet_suave, poligono_wgs84)
aet_anual <- sum(aet_mask, na.rm = TRUE)

# ------------------------------------------------------------------------------
# 5. Estadísticas por polígono
# ------------------------------------------------------------------------------
cat("5. Calculando AET mensual por polígono...\n")
extraccion_mensual <- terra::extract(aet_mask, poligono_wgs84, fun = mean, na.rm = TRUE)
tabla_mensual <- round(extraccion_mensual[, -1], 1)
tabla_final   <- cbind(Poligono = nombres_subc, tabla_mensual)
tabla_final$Total_Anual_mm <- rowSums(tabla_mensual)
names(tabla_final)[1] <- col_id

# ------------------------------------------------------------------------------
# 6. Gráficos
# ------------------------------------------------------------------------------
cat("6. Generando gráficos (300 DPI)...\n")

dibujar_mapa_anual <- function() {
  par(mar = c(2, 2, 4, 6), family = "sans")
  pal_aet <- hcl.colors(100, "YlGnBu", rev = TRUE)
  plot(aet_anual, main = "Evapotranspiración Real Acumulada Anual (mm/año)",
       col = pal_aet, axes = FALSE, box = FALSE,
       plg = list(title = " mm", cex = 0.9))
  plot(poligono_wgs84, add = TRUE, border = "gray20", lwd = 1.5)
}

dibujar_mapas_mensuales <- function() {
  pal_aet <- hcl.colors(100, "YlGnBu", rev = TRUE)
  rango_valores <- minmax(aet_mask)
  min_global <- min(rango_valores[1, ], na.rm = TRUE)
  max_global <- max(rango_valores[2, ], na.rm = TRUE)
  par(oma = c(0, 0, 4, 0), family = "sans")
  plot(aet_mask, col = pal_aet, nc = 4,
       axes = FALSE, box = FALSE,
       range = c(min_global, max_global),
       plg = list(title = "mm/mes"),
       fun = function() { plot(poligono_wgs84, add = TRUE, border = "gray20", lwd = 1) })
  mtext("Evolución Mensual de la Evapotranspiración Real (AET)",
        outer = TRUE, cex = 1.6, font = 2)
  par(oma = c(0, 0, 0, 0))
}

dibujar_barras <- function() {
  par(mar = c(4, 5, 4, 2), family = "sans")
  promedio_regional_mensual <- colMeans(tabla_mensual)
  pos_barras <- barplot(promedio_regional_mensual,
                        main = "Evolución Mensual AET (Promedio Regional)",
                        ylab = "AET (mm/mes)",
                        col = "steelblue", border = "midnightblue",
                        ylim = c(0, max(promedio_regional_mensual) * 1.2),
                        las = 1, cex.names = 0.9)
  text(x = pos_barras,
       y = promedio_regional_mensual + (max(promedio_regional_mensual) * 0.05),
       labels = round(promedio_regional_mensual, 0), cex = 0.8)
  lines(x = pos_barras, y = promedio_regional_mensual,
        col = "midnightblue", lwd = 2, lty = 2)
  points(x = pos_barras, y = promedio_regional_mensual,
         col = "midnightblue", pch = 19)
}

out_mapa_anual       <- file.path("output", "mapa_anual_aet.png")
out_mapas_mensuales  <- file.path("output", "mapas_mensuales_aet.png")
out_barras           <- file.path("output", "barras_aet.png")
out_excel            <- file.path("output", "resultados_aet_mensual.xlsx")

png(out_mapa_anual,      width = 2800, height = 1600, res = 300); dibujar_mapa_anual();      invisible(dev.off())
png(out_mapas_mensuales, width = 3600, height = 2400, res = 300); dibujar_mapas_mensuales(); invisible(dev.off())
png(out_barras,          width = 2400, height = 1600, res = 300); dibujar_barras();          invisible(dev.off())

dibujar_mapa_anual()
dibujar_mapas_mensuales()
dibujar_barras()

# ------------------------------------------------------------------------------
# 7. Excel
# ------------------------------------------------------------------------------
cat("7. Exportando Excel...\n")
write_xlsx(tabla_final, path = out_excel)

unlink(temp_nc)

cat("\n====================================================\n")
cat("PROCESO COMPLETADO\n")
cat("Archivos generados en output/:\n")
cat("  1. Mapa anual:    ", out_mapa_anual,      "\n")
cat("  2. Mapas 12 meses:", out_mapas_mensuales, "\n")
cat("  3. Barras:        ", out_barras,          "\n")
cat("  4. Excel:         ", out_excel,           "\n")
cat("====================================================\n")
