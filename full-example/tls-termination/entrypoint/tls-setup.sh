#!/bin/bash
set -e


# setup CA
cd /
if ! [ -d "/tmp/certs" ];
then
    mkdir /tmp/certs && \
    chown -R $(stat -c "%u:%g" /tmp/certs) /tmp/certs;
fi

cd /tmp/certs

if ! [ -f "/tmp/certs/testca.crt" ] ||  ! [ -f "/tmp/certs/testclient.key" ] || ! [ -f "/tmp/certs/testca.crt" ] || ! [ -f "/tmp/certs/testrproxy.crt" ];
then
    openssl genrsa -des3 -out ./testca.key -passout env:TEST_CA_PASSPHRASE 4096 && \
    openssl req -new -x509 -days 365 -key ./testca.key -out ./testca.crt -passout env:TEST_CA_PASSPHRASE -passin env:TEST_CA_PASSPHRASE -subj "/C=AU/ST=ACT/L=CBR/O=TEST_ORG_0/CN=TEST_CA" && \
    # setup test client keypair
    openssl genrsa -des3 -out testclient.key -passout env:TEST_CLIENT_PASSPHRASE 2048 && \
    openssl req -new -key testclient.key -out testclient.csr -passin env:TEST_CLIENT_PASSPHRASE -subj "/C=AU/ST=ACT/L=CBR/O=TEST_ORG_1/CN=TEST_CLIENT" && \
    openssl x509 -req -days 365 -in testclient.csr -CA testca.crt -CAkey testca.key -set_serial 01 -out testclient.crt -passin env:TEST_CA_PASSPHRASE && \
    openssl pkcs12 -export -in testclient.crt -inkey testclient.key -out testclient.p12 -passin env:TEST_CLIENT_PASSPHRASE -passout env:TEST_CLIENT_PASSPHRASE;

    # Nginx setup
    openssl req -new -nodes -keyout testrproxy.key -out ./testrproxy.csr -config /san.conf
    openssl x509 -req -days 365 -in ./testrproxy.csr -CA /tmp/certs/testca.crt -CAkey /tmp/certs/testca.key -set_serial 01 -out ./testrproxy.crt -passin env:TEST_CA_PASSPHRASE -extfile /san.conf -extensions v3_req
fi

