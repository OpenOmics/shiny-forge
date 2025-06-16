#!/usr/bin/env Rscript

# Load packages
suppressPackageStartupMessages(library(ShinyCell2, quietly = TRUE))
suppressPackageStartupMessages(library(Seurat, quietly = TRUE))
suppressPackageStartupMessages(library(optparse, quietly = TRUE))

# Misc helper functions 
options(error=function()traceback(1))
err <- function(...) { cat(sprintf(...), sep='\n', file=stderr()) }
fatal <- function(...) { err(...); quit(status = 1) }

# specify our desired options in a list
# by default OptionParser will add an 
# help option equivalent to argparse help
option_list <- list(
    make_option(
        c("-j", "--obj"),
        dest = "object",
        metavar = "Seurat Object file path",
        type = "character",
        default = NULL,
        help = "RDS file created with saveRDS containing a seurat object"
    ),
    make_option(
        c("-p", "--proj"),
        dest = "project",
        type = "character",
        metavar = "Project Name",
        default = NULL,
        help = "Project name, becomes title of the app, example: NCBR-34"
    ),
    make_option(
        "--rmmeta",
        dest = "meta.to.rm",
        metavar = "comma,delimited,metadata,column,names",
        type = "character",
        default = NULL,
        help = paste0(
            "Comma delimited list of names in seurat_object@meta.data ",
            "that will be dropped prior to deploying to ShinyCell2"
        )
    ),
    make_option(
        "--defred",
        type = "character",
        metavar = "seurat_reduction_name",
        dest = "default.reduction",
        default = NULL,
        help = paste0(
            "The default reduction to use with ShinyCell2, ",
            "this value must exist in Seurat::DefaultDimReduc(obj).\n The ",
            "two major prinipal components for this reductions must ",
            "be labeled the same label with a 1 and a 2 trailing it.\n ",
            "i.e. default.reduction = UMAP, UMAP1 and UMAP2 are the two components ",
            "that must exist"
        )
    ),
    make_option(
        c("-l", "--maxlevels"),
        type = "integer",
        dest = "max.levels",
        metavar = "MAX LEVELS [int]",
        default = NULL,
        help = paste(
            "The maximum allowable amount levels/factors of categorical values,",
            "any seurat meta.data with factors/levels greater than",
            "this number will be dropped. Default is 50. ",
            "i.e. if seurat_object@meta.data$seurat_clusters has clusters",
            "1->120 (120 factors/levels), and max levels is 50 this metadata",
            "will be discarded.", sep=" "
        )
    )
)

# get command line options, if help 
# option encountered print help and exit,
# otherwise if options not found on 
# command line then set defaults, 
opt <- parse_args(OptionParser(option_list=option_list))

# setup opt parse variables for downstream 
# usage into shinycell2
rds_file                <- opt$object
project_name            <- opt$project
required_args           <- c("object", "project")
missing_args            <- required_args[sapply(required_args, function(x) is.null(opt1[[x]]))]
if (length(missing_args) > 0) {
    cat("Error: Missing required arguments:", paste(missing_args, collapse = ", "), "\n\n")
    print_help(opt_parser1)
    quit(status = 1)
}
if (is.null(opt$meta.to.rm) | opt$meta.to.rm == "") {
    rm.meta             <- NULL
} else {
    if ("," %in% opt$meta.to.rm) {
        rm.meta         <- unlist(strsplit(opt$meta.to.rm, ",", fixed = TRUE))
    } else {
        rm.meta         <- c(trimws(gsub("[\r\n]", "", opt$meta.to.rm)))
    }
}
if (is.null(opt$default.reduction) | opt$default.reduction == "") {
    default.reduction   <- NULL
} else {
    default.reduction   <- opt$default.reduction
}
if (!is.null(opt$max.levels) | opt$max.level == "") {
    max.levels          <- opt$max.levels
} else {
    max.levels          <- NULL
}
shiny_app_dir           <- file.path("/srv/shiny-server/shinycell2")
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

# Sanity check: 
#   - Are layers (`JoinLayers` been run) joined?
#   - Does "data" layer exist?
#   - Has `FindVariableFeatures` been run?
# These are all things that ShinyCell2 checks as well, see:
#   https://github.com/the-ouyang-lab/ShinyCell2/blob/33bfc8ba232f0c829b6b23181cb83089d58e7879/R/makeShinyFilesGEX.R#L56
gex.slot = "data"
gex.assay = names(seurat_obj@assays)
if (requireNamespace("SeuratObject", quietly = TRUE)){
    gex.assay = c(SeuratObject::DefaultAssay(seurat_obj), setdiff(gex.assay, SeuratObject::DefaultAssay(seurat_obj)))
}
gex.assay = setdiff(gex.assay, "peaks")
if(!(gex.slot[1] %in% names(seurat_obj@assays[[gex.assay[1]]]@layers))){
    stop(paste0("gex.slot not found in gex.assay. ", "Are layers joined? run obj <- JoinLayers(obj)"))
}
defGenes = Seurat::VariableFeatures(seurat_obj)[1:10]
if(is.na(defGenes[1])){
    warning(paste0("Variable genes for seurat object not found! Have you ",
                    "ran `FindVariableFeatures` or `SCTransform`?"))
}

# Remove unsupported assay
# ShinyCell2 supports:
#   - CITEseq
#   - spatial
#   - scATAC (Signac)
unsupported_assays <- c("HTO")
for (assay in unsupported_assays) {
    if (assay %in% names(seurat_obj@assays)) {
        cat(paste0(assay, 'unsupported assay removed!', sep=' '))
        seurat_obj[[assay]] <- NULL
    }
}

# Create ShinyCell config file
# to make the application
config_params <- list()
if (!is.null(max.levels)) {
    config_params$maxLevels = max.levels
}

shinycell_config <- do.call(
                        createConfig,
                        c(seurat_obj, config_params)
                    )

remove_metas <- c()

if (!is.null(rm.meta)) {
    remove_metas <- c(remove_metas, rm.meta)
}

for (config_label in shinycell_config$ID) {
    for (assay in unsupported_assays) {
        if (grepl(assay, config_label, fixed = TRUE)) {
            remove_metas <- c(remove_metas, config_label)
        }
    }
}

# Build the Shiny Application,
# in the default location for
# Shiny/Posit server: i.e.
# /srv/shiny-server/${app_name}
files_params <- list(
    seurat_obj,
    shinycell_config,  
    shiny.dir = shiny_app_dir,
    shiny.prefix = "sc1",
    chunkSize = as.integer(nrow(seurat_obj@meta.data)*0.10)
)

if (!is.null(default.reduction)) {
    files_params$dimred.to.use = default.reduction
    files_params$default.dimred = c(paste0(default.reduction, '1'), paste0(default.reduction, '2'))
}

do.call(
    makeShinyFiles,
    files_params
)
makeShinyCodes(
    shiny.title = project_name,
    shiny.dir = shiny_app_dir,
    shiny.prefix = "sc1"
)

