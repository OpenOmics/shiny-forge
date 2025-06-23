# Set up

Shiny-forge is set up to work with two-stage docker images which can accept a variety
of parameters to control how an application functions.

## Applications supported

### ShinyCell

Source: https://github.com/SGDDNB/ShinyCell

#### Parameters supported

Configuration methods: https://github.com/SGDDNB/ShinyCell/blob/master/R/createConfig.R

| Parameter  |  Description  | Optional  |
|---|---|---|
| SEURAT_RDS  | Path to seurat object  |  No  |
| PROJECT_ID  | Project identifier (title)  | No  |
| DEFAULT_RED | Default dimensional reduction to use  | Yes, default is UMAP or TSNE |
| RM_META | Meta data columns to remove from Seurat object meta data tables  | Yes |
| MAX_LEVELS | Factors/levels threshold for dropping meta data |  Yes, default is 50 |

### ShinyCell2 

Source: https://github.com/the-ouyang-lab/ShinyCell2

#### Parameters supported 

Configuration methods: https://github.com/the-ouyang-lab/ShinyCell2/blob/main/R/createConfig.R

| Parameter  |  Description  | Optional  |
|---|---|---|
| SEURAT_RDS  | Path to seurat object  |  No  |
| PROJECT_ID  | Project identifier (title)  | No  |
| DEFAULT_RED | Default dimensional reduction to use  | Yes, default is UMAP or TSNE |
| RM_META | Meta data columns to remove from Seurat object meta data tables  | Yes |
| MAX_LEVELS | Factors/levels threshold for dropping meta data |  Yes, default is 50 |