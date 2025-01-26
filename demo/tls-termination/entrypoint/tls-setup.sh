#!/bin/bash
set -e

# Setup certificate dir
CERTS_DIR="/tmp/certs"
if ! [ -d "$CERTS_DIR" ]; then
    mkdir -p "$CERTS_DIR"
    chown -R $(stat -c "%u:%g" "$CERTS_DIR") "$CERTS_DIR"
fi

cd "$CERTS_DIR"

# Check if CA and client certificates exist, generate if not
if ! [ -f "$CERTS_DIR/testca.crt" ] || ! [ -f "$CERTS_DIR/testaggregator.key" ] || ! [ -f "$CERTS_DIR/testaggregator.crt" ] || ! [ -f "$CERTS_DIR/testdevice.key" ] || ! [ -f "$CERTS_DIR/testdevice.crt" ]; then
    # Generate test CA
    openssl genrsa -des3 -out "$CERTS_DIR/testca.key" -passout env:TEST_CA_PASSPHRASE 4096
    openssl req -new -x509 -days 365 -key "$CERTS_DIR/testca.key" -out "$CERTS_DIR/testca.crt" \
        -passout env:TEST_CA_PASSPHRASE -passin env:TEST_CA_PASSPHRASE \
        -subj "/C=AU/ST=ACT/L=CBR/O=TEST_ORG_0/CN=TEST_CA"

    # Setup test aggregator keypair
    openssl genrsa -des3 -out "$CERTS_DIR/testaggregator.key" -passout env:TEST_CLIENT_PASSPHRASE 2048
    openssl req -new -key "$CERTS_DIR/testaggregator.key" -out "$CERTS_DIR/testaggregator.csr" \
        -passin env:TEST_CLIENT_PASSPHRASE -subj "/C=AU/ST=ACT/L=CBR/O=TEST_ORG_1/CN=TEST_CLIENT"
    openssl x509 -req -days 365 -in "$CERTS_DIR/testaggregator.csr" -CA "$CERTS_DIR/testca.crt" \
        -CAkey "$CERTS_DIR/testca.key" -set_serial 01 -out "$CERTS_DIR/testaggregator.crt" \
        -passin env:TEST_CA_PASSPHRASE
    openssl pkcs12 -export -in "$CERTS_DIR/testaggregator.crt" -inkey "$CERTS_DIR/testaggregator.key" \
        -out "$CERTS_DIR/testaggregator.p12" -passin env:TEST_CLIENT_PASSPHRASE -passout env:TEST_CLIENT_PASSPHRASE
    rm "$CERTS_DIR/testaggregator.csr"

    # Setup test device (non-aggregator) keypair
    openssl genrsa -des3 -out "$CERTS_DIR/testdevice.key" -passout env:TEST_CLIENT_PASSPHRASE 2048
    openssl req -new -key "$CERTS_DIR/testdevice.key" -out "$CERTS_DIR/testdevice.csr" \
        -passin env:TEST_CLIENT_PASSPHRASE -subj "/C=AU/ST=ACT/L=CBR/O=TEST_ORG_1/CN=TEST_CLIENT"
    openssl x509 -req -days 365 -in "$CERTS_DIR/testdevice.csr" -CA "$CERTS_DIR/testca.crt" \
        -CAkey "$CERTS_DIR/testca.key" -set_serial 01 -out "$CERTS_DIR/testdevice.crt" \
        -passin env:TEST_CA_PASSPHRASE
    openssl pkcs12 -export -in "$CERTS_DIR/testdevice.crt" -inkey "$CERTS_DIR/testdevice.key" \
        -out "$CERTS_DIR/testdevice.p12" -passin env:TEST_CLIENT_PASSPHRASE -passout env:TEST_CLIENT_PASSPHRASE
    rm "$CERTS_DIR/testdevice.csr"
fi

# Setup dir for Nginx rproxy certs - no need to expose
RPROXY_CERTS_DIR="/tmp/rproxy_certs"
if ! [ -d "$RPROXY_CERTS_DIR" ]; then
    mkdir -p "$RPROXY_CERTS_DIR"
    chown -R $(stat -c "%u:%g" "$RPROXY_CERTS_DIR") "$RPROXY_CERTS_DIR"
fi

# Check if rproxy certs exist, generate if not
if ! [ -f "$RPROXY_CERTS_DIR/testrproxy.crt" ]; then
    openssl req -new -nodes -keyout "$RPROXY_CERTS_DIR/testrproxy.key" -out "$RPROXY_CERTS_DIR/testrproxy.csr" -config /san.conf
    openssl x509 -req -days 365 -in "$RPROXY_CERTS_DIR/testrproxy.csr" -CA "$CERTS_DIR/testca.crt" \
        -CAkey "$CERTS_DIR/testca.key" -set_serial 01 -out "$RPROXY_CERTS_DIR/testrproxy.crt" \
        -passin env:TEST_CA_PASSPHRASE -extfile /san.conf -extensions v3_req
fi
