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
        "--proj",
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
    ),
    make_option(
        c("-a", "--assay"),
        type = "character",
        dest = "assay.to.use",
        metavar = "ASSAY_NAME [str]",
        default = NULL,
        help = paste(
            "The assay to utilize for ShinyCell2 web application.",
            "Comma delimit multiple assays in a single string e.g.: RNA,spatial,ATAC,etc.", 
            "This will default to the first assay in the Seurat object (object@assays)", sep=" "
        )
    ),
    make_option(
        "--files",
        type = "character",
        dest = "shiny.files",
        metavar = "SHINY FILE [str]",
        default = NULL,
        help = paste(
            "If you have pre-build your shiny app files to save",
            "memory consumption use this key word argument to pass in",
            "the tar.gz path with files", sep=" "
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
seurat_obj              <- readRDS(rds_file)
project_name            <- opt$project
required_args           <- c("object", "project")
missing_args            <- required_args[sapply(required_args, function(x) is.null(opt[[x]]))]
shiny_app_dir           <- file.path("/srv/shiny-server/shinycell2")

if (length(missing_args) > 0) {
    cat("Error: Missing required arguments:", paste(missing_args, collapse = ", "), "\n\n")
    print_help(opt)
    quit(status = 1)
}

if (is.null(opt$shiny.files) | is.na(opt$shiny.files) | opt$shiny.files == "" | opt$shiny.files == "NA") {
    if (is.null(opt$meta.to.rm) | is.na(opt$max.levels) | opt$meta.to.rm == "" | opt$meta.to.rm == "NA") {
        rm.meta             <- NULL
    } else {
        if ("," %in% opt$meta.to.rm) {
            rm.meta         <- unlist(strsplit(opt$meta.to.rm, ",", fixed = TRUE))
        } else {
            rm.meta         <- c(trimws(gsub("[\r\n]", "", opt$meta.to.rm)))
        }
    }
    if (is.null(opt$assay.to.use) | is.na(opt$assay.to.use) | opt$assay.to.use == "" | opt$assay.to.use == "NA") {
        assay.to.use             <- NULL
    } else {
        if ("," %in% opt$assay.to.use) {
            assay.to.use         <- unlist(strsplit(opt$assay.to.use, ",", fixed = TRUE))
        } else {
            assay.to.use         <- c(trimws(gsub("[\r\n]", "", opt$assay.to.use)))
        }
    }
    if (is.null(opt$default.reduction) | is.na(opt$default.reduction) | opt$default.reduction == "" | opt$default.reduction == "NA") {
        default.reduction   <- NULL
    } else {
        if (opt$default.reduction %in% names(seurat_obj@reductions)) {
            this_key = seurat_obj@reductions[[opt$default.reduction]]@key
            default.reduction  <- c(paste0(this_key, '1'), paste0(this_key, '2'))
        } else {
            fatal(paste0('`', opt$default.reduction, '` reduction not found in seurat object!'))
        }
    }
    if (!is.null(opt$max.levels) | !is.na(opt$max.levels) | opt$max.level == "" | opt$max.level == "NA") {
        max.levels          <- opt$max.levels
    } else {
        max.levels          <- NULL
    }
    dir.create(shiny_app_dir, showWarnings = FALSE)

    # Sanity check: Does the RDS file
    # actually contain a seurat object?
    if (class(seurat_obj) == "SeuratObject"){
        # It doesn't look like it...
        err("Fatal Error: Failed to provide an RDS file with a Seuart Object.")
        fatal(" └── Please create a new RDS file with a seurat object!")
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

    shinycell_config <- delMeta(shinycell_config, remove_metas)

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
        files_params$dimred.to.use = opt$default.reduction
        files_params$default.dimred = default.reduction
    }
    if (!is.null(assay.to.use)) {
        files_params$assay = assay.to.use
    }

    do.call(
        makeShinyFiles,
        files_params
    )
} else {
    cat('Shiny files tar.gz provided - skipping object setup')
    if (!grepl("\\.tar\\.gz$", opt$shiny.files, ignore.case = TRUE) & !grepl("\\.tgz$", opt$shiny.files, ignore.case = TRUE)) {
        fatal("Error: File is not a .tar.gz or .tgz file:", opt$shiny.files, "\nFile must have .tar.gz or .tgz extension\n")
    }
    cat("Extracting", opt$shiny.files, "to", shiny_app_dir, "\n")
    untar(tarfile = opt$shiny.files, exdir = shiny_app_dir, compressed=TRUE)
    cat("Successfully extracted!\n")
}
makeShinyCodes(
    shiny.title = project_name,
    shiny.dir = shiny_app_dir,
    shiny.prefix = "sc1"
)

