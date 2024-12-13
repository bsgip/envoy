#!/bin/bash

export HOST_UID=$(id -u)
export HOST_GID=$(id -g)
docker-compose -f docker-compose.complete-example.yaml down
docker-compose -f docker-compose.complete-example.yaml up -d