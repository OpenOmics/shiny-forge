FROM gcr.io/openomics-gcp/shinycell2-base:latest
ADD Dockerfile /opt2/shinycell2.app.dockerfile
ENV R_MAX_VSIZE=64000000000
############### ARGS ################
# RDS file containing a Seurat object
ARG SEURAT_RDS
# Project identifer, becomes title of
# Shiny application
ARG PROJECT_ID
ARG DEFAULT_RED="NA"
ARG RM_META="NA"
ARG MAX_LEVELS="NA"
ARG SEURAT_ASSAY="NA"
ARG SHINY_FILES="NA"
############## SETUP ################
# Copy the Seurat RDS file
COPY --chmod=777 "${SEURAT_RDS}" /opt2/seurat_object.rds
RUN mkdir -p /data/aux
COPY ${SHINY_FILES} /data/aux/
USER root
RUN chown -R shinyuser:shiny /srv/shiny-server /opt2
USER shinyuser
RUN Rscript /opt2/build_shinycell.R \
        --obj /opt2/seurat_object.rds \
        --proj "${PROJECT_ID}" \
        --rmmeta "${RM_META}" \
        --defred "${DEFAULT_RED}" \
        --maxlevels "${MAX_LEVELS}" \
        --files "${SHINY_FILES}" \
        && rm /opt2/seurat_object.rds
# Listen on port for incoming connections
EXPOSE 8080
# Add healthcheck to ensure container is 
# running and ready to accept connections,
# if not exit with non-zero exit code. This
# is useful for orchestration tools that 
# require need a healthcheck to determine
# if the container is ready to accept 
# connections. If the healthcheck fails 
# after 3 retries the container will be 
# automatically restarted.
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
          CMD curl -f http://localhost:8080 \
          || (echo 'Error: Health check failed, unable to reach Shiny app on port 8080!' >&2 && exit 1)
# Run the ShinyCell application
CMD ["R", "-e", "shiny::runApp('/srv/shiny-server/shinycell2', port=8080, host='0.0.0.0')"]