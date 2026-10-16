#!/usr/bin/env bash
# (Re)generates a throwaway CA and a server certificate signed by it into .local/tls/
# (same layout as a cert-manager secret: ca.crt, tls.crt, tls.key).
# Files are swapped in via rename, so this can also be used to test live cert rotation
# against a running container (see server.sh, which mounts .local/tls).

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../../.."

OUT_DIR=${OUT_DIR:-.local/tls}
CA_DAYS=${CA_DAYS:-90}
CERT_DAYS=${CERT_DAYS:-30}
CERT_CN=${CERT_CN:-localhost}
CERT_SAN=${CERT_SAN:-DNS:localhost,DNS:test,IP:127.0.0.1,IP:::1}

GENERATION=$(date +%s)

mkdir -p "$OUT_DIR"
TMP_DIR=$(mktemp -d "$OUT_DIR/.gencerts.XXXXXX")
trap 'rm -rf "$TMP_DIR"' EXIT

# CA (its key is discarded: just regenerate everything when needed)
openssl req -x509 -newkey rsa:2048 -nodes \
    -keyout "$TMP_DIR/ca.key" -out "$TMP_DIR/ca.crt" \
    -days "$CA_DAYS" \
    -subj "/CN=alertmanager-graphmail-forwarder-ca/description=generated $GENERATION" \
    -addext "basicConstraints=critical,CA:TRUE" \
    -addext "keyUsage=critical,digitalSignature,keyCertSign,cRLSign" \
    2>/dev/null

# server key + certificate signed by the CA
openssl req -newkey rsa:2048 -nodes \
    -keyout "$TMP_DIR/tls.key" -out "$TMP_DIR/tls.csr" \
    -subj "/CN=$CERT_CN/description=generated $GENERATION" \
    2>/dev/null
openssl x509 -req -in "$TMP_DIR/tls.csr" \
    -CA "$TMP_DIR/ca.crt" -CAkey "$TMP_DIR/ca.key" -CAcreateserial \
    -out "$TMP_DIR/tls.crt" \
    -days "$CERT_DAYS" \
    -extfile <(printf '%s\n' \
        "basicConstraints=critical,CA:FALSE" \
        "keyUsage=critical,digitalSignature,keyEncipherment" \
        "extendedKeyUsage=serverAuth" \
        "subjectAltName=$CERT_SAN") \
    2>/dev/null

openssl verify -CAfile "$TMP_DIR/ca.crt" "$TMP_DIR/tls.crt" >/dev/null

# the container runs as uid 1000 and must be able to read the key via the bind mount
chmod 0644 "$TMP_DIR/ca.crt" "$TMP_DIR/tls.crt" "$TMP_DIR/tls.key"

mv -f "$TMP_DIR/ca.crt" "$OUT_DIR/ca.crt"
mv -f "$TMP_DIR/tls.key" "$OUT_DIR/tls.key"
mv -f "$TMP_DIR/tls.crt" "$OUT_DIR/tls.crt"

echo "Generated certificates in $OUT_DIR:"
openssl x509 -in "$OUT_DIR/tls.crt" -noout -subject -issuer -enddate -ext subjectAltName
