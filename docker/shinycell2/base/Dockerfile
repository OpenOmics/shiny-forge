# Base image for shinycell, uses 
# rocker/shiny:v4.4.3 as base image
# which uses Ubuntu/24.04 (noble)
FROM rocker/shiny:4.4.3

############### ABOUT ###############
# Depedencies of ShinyCell2:
# • https://github.com/the-ouyang-lab/ShinyCell2
# @TLDR:
#    • R already satisfied: 4.4.3
#        • data.table
#        • DT
#        • Matrix
#        • hdf5r
#        • reticulate
#        • ggplot2
#        • gridExtra
#        • glue
#        • readr
#        • RColorBrewer
#        • R.utils
#        • Seurat
#        • shiny
#        • magrittr
#        • ggdendro
#        • ShinyCell
LABEL maintainer="Skyler Kuhn <kuhnsa@nih.gov>, Ryan Routsong <routsongrm@nih.gov>"

############### INIT ################
# Create Container filesystem specific 
# working directory and opt directories
# to avoid collisions with the host's
# filesystem, i.e. /opt and /data
RUN mkdir -p /opt2/work && mkdir -p /data2 
WORKDIR /opt2 

# Set time zone to US east coast 
ENV TZ=America/New_York
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
        && echo $TZ > /etc/timezone

############### DEPS ################
# This section installs system packages 
# required for your project. If you need 
# extra system packages add them here.
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y \
        build-essential \
        bzip2 \
        ca-certificates \
        cmake \
        curl \
        gawk \
        git \
        gzip \
        libfreetype6-dev \
        libgit2-dev \
        libpng-dev \
        libtiff5-dev \
        libjpeg-dev \
        libharfbuzz-dev \
        libfribidi-dev \
        libhdf5-dev \
        libxml2-dev \
        locales \
        make \
        python3 \
        python3-pip \
        unzip \
        wget \
        zlib1g-dev \
        libglpk-dev \
    && apt-get clean && apt-get purge \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Set the locale
RUN localedef -i en_US -f UTF-8 en_US.UTF-8

# Make python3 the default interpreter
# and install Python Packages 
RUN ln -sf /usr/bin/python3 /usr/bin/python

############### INSTALL ################
# Install GNU which, increases compatiability
# with which distros included with Debian/Rocky
# linux installations, this version of which
# includes extra options that the ubuntu version 
# does not have. The gnu verison is backwards 
# compatiable with the ubunutu version.
RUN mkdir -p /opt2/ \
        && wget --no-check-certificate -O /opt2/which.tar.gz https://ftp.gnu.org/gnu/which/which-2.21.tar.gz \
        && tar -xvf /opt2/which.tar.gz -C /opt2/ \
        && rm /opt2/which.tar.gz \
        && cd /opt2/which-2.21/ \
        && ./configure --prefix=/opt2/which-2.21 \
        && make \
        && make install

# Install ShinyCell from Github,
# https://github.com/SGDDNB/ShinyCell
# Copy R script to install packages
COPY install_packages.R /opt2/install_packages.R
RUN cd /opt2 && Rscript /opt2/install_packages.R 
RUN Rscript -e 'devtools::install_github("OpenOmics/ShinyCell2")'
COPY git_installs.sh /opt2/work/git_installs.sh
RUN cd /opt2/work; ./git_installs.sh
COPY build_shinycell.R /opt2/build_shinycell.R

################ POST #################
# Add Dockerfile and export important 
# environment variables
ADD Dockerfile /opt2/shinycell2.base.dockerfile
RUN chmod -R a+rX /opt2 /srv/shiny-server; chmod -R g+wX /srv/shiny-server
ENV PATH="/opt2/which-2.21/bin:${PATH}"
WORKDIR /data2

# Create a non-root user, shinyuser,
# to run the Shiny application
RUN useradd -ms /bin/bash shinyuser
RUN usermod -a -G shiny shinyuser
RUN chown -R shinyuser:shiny /srv/shiny-server /opt2
USER shinyuser
