#!/usr/bin/env Rscript
suppressMessages(library(ShinyCell, quietly = TRUE))
suppressMessages(library(optparse, quietly = TRUE))

# Misc helper functions 
options(error=function()traceback(1))
err <- function(...){cat(sprintf(...), sep='\n', file=stderr())}
fatal <- function(...) {err(...); quit(status = 1)}

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
            "that will be dropped prior to deploying to ShinyCell"
        )
    ),
    make_option(
        "--defred",
        type = "character",
        metavar = "seurat_reduction_name",
        dest = "default.reduction",
        default = NULL,
        help = paste0(
            "The default reduction to use with ShinyCell, ",
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
# usage into shinycell
rds_file                <- opt$object
project_name            <- opt$project
required_args           <- c("object", "project")
missing_args            <- required_args[sapply(required_args, function(x) is.null(opt[[x]]))]
if (length(missing_args) > 0) {
    cat("Error: Missing required arguments:", paste(missing_args, collapse = ", "), "\n\n")
    print_help(opt)
    quit(status = 1)
}
# Read in file with seurat object
seurat_obj <- readRDS(rds_file)

if (is.null(opt$meta.to.rm) | is.na(opt$max.levels) | opt$meta.to.rm == "" | opt$meta.to.rm == "NA") {
    rm.meta             <- NULL
} else {
    if ("," %in% opt$meta.to.rm) {
        rm.meta         <- unlist(strsplit(opt$meta.to.rm, ",", fixed = TRUE))
    } else {
        rm.meta         <- c(trimws(gsub("[\r\n]", "", opt$meta.to.rm)))
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
    max.levels          <- 50
}

config_params <- list()
if (!is.null(max.levels)) {
    config_params$maxLevels = max.levels
}
metas = colnames(seurat_obj@meta.data)
newmetas <- metas
if (!is.null(rm.meta)) {
    newmetas = c()
    for (meta in metas) {
        if (!meta %in% rm.meta) {
            newmetas = c(newmetas, meta)
        }
    }
}
config_params$meta.to.include = newmetas

# Create ShinyCell config file
# to make the application
shinycell_config <- do.call(
                        createConfig,
                        c(seurat_obj, config_params)
                    )

# Build the Shiny Application,
# in the default location for
# Shiny/Posit server: i.e.
# /srv/shiny-server/${app_name}

app_params = list(seurat_obj, shinycell_config)
if (!is.null(default.reduction)) {
    app_params$default.dimred = default.reduction
}

dir.create("/srv/shiny-server", showWarnings = FALSE)
app_params$gene.mapping = TRUE
app_params$shiny.title = project_name
app_params$shiny.dir = "/srv/shiny-server/shinycell/"

do.call(
    makeShinyApp,
    app_params
)
