#!/usr/bin/env Rscript

# Install from Github via devtools
library(ShinyCell2)
library(Seurat)

# Misc helper functions 
err <- function(...){cat(sprintf(...), sep='\n', file=stderr())}
fatal <- function(...) {err(...); quit(status = 1)}

# Parse command line arguments,
# may want to add more cli options
# to allow a user to set extra
# parameters for the createConfig
# and makeShinyApp R functions
args <- commandArgs(
    trailingOnly = TRUE
)

# Sanity check for correct usage 
# of program, were all required 
# positional args provided
if (length(args) != 2) {
    err("Usage: build_shinycell.R <RDS_FILE_WITH_SEURAT_OBJECT> <PROJECT_ID>\n")
    err("Fatal Error: Missing required positional arguments.")
    err(" └── Please provide both required command line arguments and try again!\n")
    fatal("Example: build_shinycell.R /path/to/seurat_obj.rds 'NCBR-0: ShinyCell'")
} 

rds_file      <- args[1]     # RDS file created with saveRDS containing a seurat object
project_name  <- args[2]     # Project name, becomes title of the app, example: NCBR-34
shiny_app_dir <- file.path("/srv/shiny-server/shinycell2")
dir.create(shiny_app_dir, showWarnings = FALSE)

# Read in file with seurat object
seurat_obj <- readRDS(rds_file)

# Sanity check: Does the RDS file
# actually contain a seurat object?
if (class(seurat_obj) == "SeuratObject"){
    # It doesn't look like it...
    err("Fatal Error: Failed to provide an RDS file with a Seuart Object.")
    fatal(" └── Please create a new RDS file with a seurat object!")
}

unsupported_assays <- c("HTO")

for (assay in unsupported_assays) {
    if (assay %in% names(seurat_obj@assays)) {
        cat(paste0(assay, 'unsupported assay removed!', sep=' '))
        seurat_obj[[assay]] <- NULL
    }
}

# Create ShinyCell config file
# to make the application
shinycell_config <- createConfig(seurat_obj)

remove_metas <- c()

for (config_label in shinycell_config$ID) {
    for (assay in unsupported_assays) {
        if (grepl(assay, config_label, fixed = TRUE)) {
            remove_metas <- c(remove_metas, config_label)
        }
    }
}

for (label in remove_metas) {
    if (label %in% shinycell_config$ID) {
        cat(paste0('Removing ', label, ' meta.data from seurat object'))
        shinycell_config <- delMeta(shinycell_config, label)
    }
}

# Build the Shiny Application,
# in the default location for
# Shiny/Posit server: i.e.
# /srv/shiny-server/${app_name}
makeShinyFiles(
    seurat_obj, 
    shinycell_config, 
    shiny.dir = shiny_app_dir,
    shiny.prefix = "sc1",
    chunkSize = 5000,
)
makeShinyCodes(
    shiny.title = project_name,
    shiny.dir = shiny_app_dir,
    shiny.prefix = "sc1"
)
