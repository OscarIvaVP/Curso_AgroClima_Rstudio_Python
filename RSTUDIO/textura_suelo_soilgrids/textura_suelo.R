# ==============================================================================
# TEXTURA DEL SUELO POR SUBCUENCA (SoilGrids / VRT virtuales)
#
# Convenciones del proyecto:
#   - input/   (tú creas esta carpeta y pones ahí el shapefile multipolígono)
#   - output/  (se crea automáticamente al ejecutar)
#
# Configuración:
#   - COL_ID: nombre de la columna que identifica cada polígono.
#       NULL  -> el script te preguntará con un diálogo (RStudio).
#       "xxx" -> usa esa columna directamente si existe.
# ==============================================================================

# install.packages(c("sf", "soiltexture", "terra", "writexl"))

library(sf)
library(soiltexture)
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
    stop(sprintf("No existe la carpeta '%s/'. Créala y coloca ahí tu shapefile.", dir_input))
  }
  shps <- list.files(dir_input, pattern = "\\.shp$", full.names = TRUE, recursive = TRUE)
  if (length(shps) == 0) stop(sprintf("No se encontró ningún .shp dentro de '%s/'.", dir_input))
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
# 1. Shapefile
# ------------------------------------------------------------------------------
cat("1. Cargando shapefile desde input/...\n")
ruta_shp <- encontrar_shapefile("input")
poligono <- st_read(ruta_shp, quiet = TRUE)
col_id <- elegir_columna(poligono, COL_ID)

poligono_vect <- vect(poligono)
dir.create("output", showWarnings = FALSE, recursive = TRUE)

# ------------------------------------------------------------------------------
# 2. SoilGrids
# ------------------------------------------------------------------------------
cat("2. Conectando a SoilGrids (/vsicurl/)...\n")
url_sand <- "/vsicurl/https://files.isric.org/soilgrids/latest/data/sand/sand_0-5cm_mean.vrt"
url_silt <- "/vsicurl/https://files.isric.org/soilgrids/latest/data/silt/silt_0-5cm_mean.vrt"
url_clay <- "/vsicurl/https://files.isric.org/soilgrids/latest/data/clay/clay_0-5cm_mean.vrt"
r_sand <- rast(url_sand); r_silt <- rast(url_silt); r_clay <- rast(url_clay)

# ------------------------------------------------------------------------------
# 3. Reproyectar al CRS de SoilGrids
# ------------------------------------------------------------------------------
cat("3. Reproyectando al CRS de SoilGrids...\n")
poligono_vect_proj <- project(poligono_vect, crs(r_sand))

# ------------------------------------------------------------------------------
# 4. Recortar y enmascarar
# ------------------------------------------------------------------------------
cat("4. Recortando los mapas globales al polígono...\n")
sand_crop <- crop(r_sand, poligono_vect_proj, mask = TRUE)
silt_crop <- crop(r_silt, poligono_vect_proj, mask = TRUE)
clay_crop <- crop(r_clay, poligono_vect_proj, mask = TRUE)

# ------------------------------------------------------------------------------
# 5. Estadísticas por sub-polígono
# ------------------------------------------------------------------------------
cat("5. Calculando promedios y SD por polígono...\n")
ext_sand    <- terra::extract(sand_crop, poligono_vect_proj, fun = mean, na.rm = TRUE)
ext_silt    <- terra::extract(silt_crop, poligono_vect_proj, fun = mean, na.rm = TRUE)
ext_clay    <- terra::extract(clay_crop, poligono_vect_proj, fun = mean, na.rm = TRUE)
ext_sand_sd <- terra::extract(sand_crop, poligono_vect_proj, fun = sd,   na.rm = TRUE)
ext_silt_sd <- terra::extract(silt_crop, poligono_vect_proj, fun = sd,   na.rm = TRUE)
ext_clay_sd <- terra::extract(clay_crop, poligono_vect_proj, fun = sd,   na.rm = TRUE)

arena_media   <- ext_sand[, 2] / 10
limo_medio    <- ext_silt[, 2] / 10
arcilla_media <- ext_clay[, 2] / 10
arena_sd      <- ext_sand_sd[, 2] / 10
limo_sd       <- ext_silt_sd[, 2] / 10
arcilla_sd    <- ext_clay_sd[, 2] / 10

nombres_subc <- as.character(poligono_vect_proj[[col_id]][[1]])

datos_textura <- data.frame(SAND = arena_media, SILT = limo_medio, CLAY = arcilla_media)
clases_finales <- TT.points.in.classes(
  tri.data = datos_textura, class.sys = "USDA.TT", PiC.type = "t"
)

cat(sprintf("\nAnálisis completado para %d sub-polígonos.\n", length(nombres_subc)))

# ------------------------------------------------------------------------------
# 6. Gráficos
# ------------------------------------------------------------------------------
cat("6. Generando gráficos (300 DPI)...\n")

out_mapas  <- file.path("output", "mapas_textura_publicacion.png")
out_barras <- file.path("output", "grafico_barras_subcuencas.png")
out_excel  <- file.path("output", "resultados_textura_subcuencas.xlsx")

dibujar_mapas_profesionales <- function() {
  par(mfrow = c(2, 2), mar = c(4, 1, 3, 1), oma = c(0, 0, 4, 0), family = "sans")
  pal_arena   <- hcl.colors(100, "YlOrBr", rev = TRUE)
  pal_limo    <- hcl.colors(100, "YlGnBu", rev = TRUE)
  pal_arcilla <- hcl.colors(100, "Reds",   rev = TRUE)

  plot(sand_crop / 10, main = "Contenido de Arena (%)", col = pal_arena,
       axes = FALSE, box = FALSE, plg = list(loc = "bottom", title = "%", cex = 0.9))
  plot(poligono_vect_proj, add = TRUE, border = "gray20", lwd = 1.2)

  plot(silt_crop / 10, main = "Contenido de Limo (%)", col = pal_limo,
       axes = FALSE, box = FALSE, plg = list(loc = "bottom", title = "%", cex = 0.9))
  plot(poligono_vect_proj, add = TRUE, border = "gray20", lwd = 1.2)

  plot(clay_crop / 10, main = "Contenido de Arcilla (%)", col = pal_arcilla,
       axes = FALSE, box = FALSE, plg = list(loc = "bottom", title = "%", cex = 0.9))
  plot(poligono_vect_proj, add = TRUE, border = "gray20", lwd = 1.2)

  TT.plot(class.sys = "USDA.TT", tri.data = datos_textura,
          main = "Clasificación Textural USDA",
          col = rgb(0.1, 0.4, 0.8, alpha = 0.6), pch = 19, cex = 1.6,
          cex.axis = 0.8, cex.lab = 0.9, cex.main = 1.2,
          arrows.show = FALSE, grid.show = TRUE,
          grid.col = "gray85", class.line.col = "black")
  mtext("Distribución Espacial de Textura del Suelo por Polígono",
        outer = TRUE, cex = 1.6, font = 2)
  par(mfrow = c(1, 1), oma = c(0, 0, 0, 0))
}

dibujar_barras_composicion <- function() {
  matriz_barras <- t(as.matrix(datos_textura))
  colnames(matriz_barras) <- nombres_subc
  par(mar = c(12, 5, 6, 2), family = "sans")
  colores_barras <- c("#E69F00", "#7FC97F", "#E31A1C")
  barplot(matriz_barras,
          main = "Composición Textural Promedio por Polígono",
          ylab = "Proporción (%)",
          col = colores_barras, border = "white",
          las = 2, cex.names = 0.8, space = 0.2)
  legend("top", inset = c(0, -0.15),
         legend = c("Arena", "Limo", "Arcilla"),
         fill = colores_barras, border = "white", bty = "n",
         xpd = TRUE, cex = 1.1, horiz = TRUE)
}

png(out_mapas,  width = 3200, height = 2400, res = 300); dibujar_mapas_profesionales(); invisible(dev.off())
png(out_barras, width = 2800, height = 2000, res = 300); dibujar_barras_composicion();  invisible(dev.off())

dibujar_mapas_profesionales()
dibujar_barras_composicion()

# ------------------------------------------------------------------------------
# 7. Excel
# ------------------------------------------------------------------------------
datos_exportar <- data.frame(
  Poligono             = nombres_subc,
  Arena_Promedio_Pct   = round(arena_media, 2),
  Arena_SD             = round(arena_sd, 2),
  Limo_Promedio_Pct    = round(limo_medio, 2),
  Limo_SD              = round(limo_sd, 2),
  Arcilla_Promedio_Pct = round(arcilla_media, 2),
  Arcilla_SD           = round(arcilla_sd, 2),
  Clase_Textural_USDA  = clases_finales
)
names(datos_exportar)[1] <- col_id
write_xlsx(datos_exportar, path = out_excel)

cat("\n====================================================\n")
cat("PROCESO COMPLETADO\n")
cat("Archivos generados en output/:\n")
cat("  1. Mapas: ", out_mapas,  "\n")
cat("  2. Barras:", out_barras, "\n")
cat("  3. Excel: ", out_excel,  "\n")
cat("====================================================\n")
