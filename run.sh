#!/bin/bash

# Construir la imagen Docker
docker build -t scrapuv .

# Ejecutar el contenedor
docker run -d --name scrapuv_container scrapuv
