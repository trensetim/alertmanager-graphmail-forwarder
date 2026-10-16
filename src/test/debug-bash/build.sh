#!/usr/bin/env bash

IMAGE_NAME=${IMAGE_NAME:-agf:local}

cd "$(dirname "${BASH_SOURCE[0]}")/../../.."
sed 's|^RUN pip install|RUN --mount=type=secret,id=ca export SSL_CERT_FILE=/run/secrets/ca PIP_CERT=/run/secrets/ca \&\& pip install|' src/build/docker/Dockerfile \
    | docker build \
        --secret id=ca,src=/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem \
        -f - \
        -t "${IMAGE_NAME}" \
        .
