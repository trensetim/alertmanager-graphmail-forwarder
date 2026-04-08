#!/bin/bash

# must be run from project root

IMAGE_NAME="proxyimg"
docker build -t "$IMAGE_NAME" -f src/build/docker/Dockerfile .

source .env
docker run --rm -it -p "$LISTEN_PORT:$LISTEN_PORT" \
    -e LISTEN_PORT="$LISTEN_PORT" \
    -e TENANT_ID="$TENANT_ID" \
    -e CLIENT_ID="$CLIENT_ID" \
    -e CLIENT_SECRET="$CLIENT_SECRET" \
    -e FROM="$FROM" \
    -e TO="$TO" \
    -e AUTH_TOKEN="$AUTH_TOKEN" \
    -v $(pwd)/.local/tls:/app/tls:ro \
    "$IMAGE_NAME"
