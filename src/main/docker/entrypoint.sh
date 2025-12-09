#!/bin/sh

# configure env defaults
export HTTP_TIMEOUT_SECONDS=${HTTP_TIMEOUT_SECONDS:-10.0}
export LISTEN_ADDRESS=${LISTEN_ADDRESS:-0.0.0.0}
export LISTEN_PORT=${LISTEN_PORT:-8080}

gunicorn -k gthread -b $LISTEN_ADDRESS:$LISTEN_PORT main:flask
