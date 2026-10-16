#!/bin/bash

cd "$(dirname "${BASH_SOURCE[0]}")/../../.."

IMAGE_NAME=${IMAGE_NAME:-agf:local}
./src/test/debug-bash/build.sh

LOG_LEVEL=${LOG_LEVEL:-info}

source .env
docker run --rm -it -p "$LISTEN_PORT:$LISTEN_PORT" \
    -e LISTEN_PORT="$LISTEN_PORT" \
    -e TENANT_ID="$TENANT_ID" \
    -e CLIENT_ID="$CLIENT_ID" \
    -e CLIENT_SECRET="$CLIENT_SECRET" \
    -e FROM="$FROM" \
    -e TO="$TO" \
    -e AUTH_TOKEN="$AUTH_TOKEN" \
    -e LOG_LEVEL="$LOG_LEVEL" \
    -v $(pwd)/.local/tls:/app/tls:ro \
    "$IMAGE_NAME"
