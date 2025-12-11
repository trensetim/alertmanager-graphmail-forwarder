#!/bin/sh

# configure env defaults
export HTTP_TIMEOUT_SECONDS=${HTTP_TIMEOUT_SECONDS:-10.0}
export LISTEN_ADDRESS=${LISTEN_ADDRESS:-0.0.0.0}
export LISTEN_PORT=${LISTEN_PORT:-8080}

if [ -e "./tls/crt.pem" ] && [ -e "./tls/key.pem" ] && [ -z "$TLS_CERT_PATH" ] && [ -z "$TLS_KEY_PATH" ]; then
    # automatically enable TLS if cert and key files are present and the environment variables are unset
    export TLS_CERT_PATH="./tls/crt.pem"
    export TLS_KEY_PATH="./tls/key.pem"
    TLS_CLIARGS="--certfile $TLS_CERT_PATH --keyfile $TLS_KEY_PATH"
elif [ -n "$TLS_CERT_PATH" ] || [ -n "$TLS_KEY_PATH" ]; then
    # use provided TLS cert and key paths
    export TLS_CERT_PATH="${TLS_CERT_PATH:-./tls/crt.pem}"
    export TLS_KEY_PATH="${TLS_KEY_PATH:-./tls/key.pem}"
    TLS_CLIARGS="--certfile $TLS_CERT_PATH --keyfile $TLS_KEY_PATH"
else
    # no TLS
    TLS_CLIARGS=""
fi

exec gunicorn \
    -k gthread \
    -b $LISTEN_ADDRESS:$LISTEN_PORT \
    $TLS_CLIARGS \
    main:flask
