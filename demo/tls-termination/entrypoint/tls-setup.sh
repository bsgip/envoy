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
if ! [ -f "$CERTS_DIR/testca.crt" ] || ! [ -f "$CERTS_DIR/testaggregator.key" ] || ! [ -f "$CERTS_DIR/testaggregator.crt" ] || ! [ -f "$CERTS_DIR/testdevice1.key" ] || ! [ -f "$CERTS_DIR/testdevice1.crt" ] || ! [ -f "$CERTS_DIR/testdevice2.key" ] || ! [ -f "$CERTS_DIR/testdevice2.crt" ]; then
    # Generate test CA
    openssl genrsa -out "$CERTS_DIR/testca.key" 4096
    openssl req -new -x509 -days 9999 -key "$CERTS_DIR/testca.key" -out "$CERTS_DIR/testca.crt" \
        -subj "/C=AU/ST=ACT/L=CBR/O=TEST_ORG_0/CN=TEST_CA"

    # Setup test aggregator keypair
    openssl genrsa -out "$CERTS_DIR/testaggregator.key" 2048
    openssl req -new -key "$CERTS_DIR/testaggregator.key" -out "$CERTS_DIR/testaggregator.csr" \
        -subj "/C=AU/ST=ACT/L=CBR/O=TEST_ORG_1/CN=TEST_AGG"
    openssl x509 -req -days 9999 -in "$CERTS_DIR/testaggregator.csr" -CA "$CERTS_DIR/testca.crt" \
        -CAkey "$CERTS_DIR/testca.key" -set_serial 01 -out "$CERTS_DIR/testaggregator.crt"
    openssl pkcs12 -export -in "$CERTS_DIR/testaggregator.crt" -inkey "$CERTS_DIR/testaggregator.key" \
        -out "$CERTS_DIR/testaggregator.p12" -passout pass:
    rm "$CERTS_DIR/testaggregator.csr"

    # Setup test device (non-aggregator) keypair (device1)
    openssl genrsa -out "$CERTS_DIR/testdevice1.key" 2048
    openssl req -new -key "$CERTS_DIR/testdevice1.key" -out "$CERTS_DIR/testdevice1.csr" \
        -subj "/C=AU/ST=ACT/L=CBR/O=TEST_ORG_1/CN=TEST_DEVICE1"
    openssl x509 -req -days 9999 -in "$CERTS_DIR/testdevice1.csr" -CA "$CERTS_DIR/testca.crt" \
        -CAkey "$CERTS_DIR/testca.key" -set_serial 02 -out "$CERTS_DIR/testdevice1.crt" 
    openssl pkcs12 -export -in "$CERTS_DIR/testdevice1.crt" -inkey "$CERTS_DIR/testdevice1.key" \
        -out "$CERTS_DIR/testdevice1.p12" -passout pass:
    rm "$CERTS_DIR/testdevice1.csr"

    # Setup test device (non-aggregator) keypair (device2)
    openssl genrsa -out "$CERTS_DIR/testdevice2.key" 2048
    openssl req -new -key "$CERTS_DIR/testdevice2.key" -out "$CERTS_DIR/testdevice2.csr" \
        -subj "/C=AU/ST=ACT/L=CBR/O=TEST_ORG_1/CN=TEST_DEVICE2"
    openssl x509 -req -days 9999 -in "$CERTS_DIR/testdevice2.csr" -CA "$CERTS_DIR/testca.crt" \
        -CAkey "$CERTS_DIR/testca.key" -set_serial 03 -out "$CERTS_DIR/testdevice2.crt" 
    openssl pkcs12 -export -in "$CERTS_DIR/testdevice2.crt" -inkey "$CERTS_DIR/testdevice2.key" \
        -out "$CERTS_DIR/testdevice2.p12" -passout pass:
    rm "$CERTS_DIR/testdevice2.csr"
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
        -extfile /san.conf -extensions v3_req
fi
