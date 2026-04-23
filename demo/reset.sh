#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

docker build --pull --no-cache -t envoy:latest -f ../Dockerfile.server ../

HOST_UID=$(id -u) HOST_GID=$(id -g) docker compose down -v

HOST_UID=$(id -u) HOST_GID=$(id -g) docker compose up -d --build

echo ""
echo "Stack is up. Smoke test with:"
echo "  curl --cacert ./tls-termination/test_certs/testca.crt --cert ./tls-termination/test_certs/testdevice1.p12: --cert-type p12 https://localhost:8443/dcap"
