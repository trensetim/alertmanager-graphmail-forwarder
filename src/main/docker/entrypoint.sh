#!/bin/sh

# configure env defaults
export HTTP_TIMEOUT_SECONDS=${HTTP_TIMEOUT_SECONDS:-10.0}
export LISTEN_ADDRESS=${LISTEN_ADDRESS:-0.0.0.0}
export LISTEN_PORT=${LISTEN_PORT:-8080}

function watch_tls_cert {
    # monitor TLS certificate files and restart the server if they change
    while true; do
        inotifywait \
            -e modify,create,delete,attrib,moved_to \
            $(dirname "$TLS_CERT_PATH")

        echo "TLS certificate changed, restarting server..."
        sleep 1  # settle during multiple rapid changes
        pkill -USR2 -e gunicorn
    done
}

if [ -e "./tls/tls.crt" ] && [ -e "./tls/tls.key" ] && [ -z "$TLS_CERT_PATH" ] && [ -z "$TLS_KEY_PATH" ]; then
    # automatically enable TLS if cert and key files are present and the environment variables are unset
    export TLS_CERT_PATH="./tls/tls.crt"
    export TLS_KEY_PATH="./tls/tls.key"
    TLS_CLIARGS="--certfile $TLS_CERT_PATH --keyfile $TLS_KEY_PATH"
    watch_tls_cert &
elif [ -n "$TLS_CERT_PATH" ] || [ -n "$TLS_KEY_PATH" ]; then
    # use provided TLS cert and key paths
    export TLS_CERT_PATH="${TLS_CERT_PATH:-./tls/tls.crt}"
    export TLS_KEY_PATH="${TLS_KEY_PATH:-./tls/tls.key}"
    TLS_CLIARGS="--certfile $TLS_CERT_PATH --keyfile $TLS_KEY_PATH"
    watch_tls_cert &
else
    # no TLS
    TLS_CLIARGS=""
fi

# we use the default 1 worker & 1 thread, because the application relies on in-process direct function calls
exec gunicorn \
    -b $LISTEN_ADDRESS:$LISTEN_PORT \
    $TLS_CLIARGS \
    main:flask
