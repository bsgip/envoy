# envoy demo server

This demo is designed to allow you to quickly evaluate the envoy server in a local development environment. It is not a "production grade" docker compose file. It's purely a way to quickly startup and evaluate the csip-aus implementation.

## Starting the demo

You will need [Docker](https://www.docker.com/) to run this demo

**To start the demo:**

You will need to build an image called `envoy:latest` and then up the compose file:

```
# Run all the demo commands from the demo/ directory
cd demo/

# Build the default envoy image
docker build -t envoy:latest -f ../Dockerfile.server ../

# Up the demo compose file
HOST_UID=$(id -u) HOST_GID=$(id -g) docker compose up
```

This will start the following services:
* [nginx](https://nginx.org/): for providing TLS validation/termination
    * testing client certificates and keys will generate in `./tls-termination/test_certs/`
    * Will expose and listen on port `8443`
    * Will only accept TLS connections with a client cert that has been signed by the "test CA" (see below)
* [postgres](https://www.postgresql.org/): As the database provider
    * Database will be exposed to the host machine and accessible using: `postgresql+asyncpg://test_user:test_pwd@localhost:8003/test_db`
* [RabbitMQ](https://www.rabbitmq.com/): As the messaging broker (underlies 2030.5 pub/sub)
* envoy: Requests are expected to be proxied through nginx as that will handle all of the certificate validation.
    *  Port `8000` will allow requests to access envoy directly but will require manually specifying `x-forwarded-client-cert`
* envoy-admin:
    * Port `8001` will allow requests to access the envoy-admin API directly.


## Client Certificates

The underlying IEEE 2030.5 standard requires specially signed certificates to identify clients. When this example is first executed, it will create the following files in the directory:

`tls-termination/test_certs/`

| File | Description |
|------|-------------|
| `testca.crt` | Certificate for the self signed certificate authority (CA) that will be signing the client/proxy certs |
| `testca.key` | Private Key for the self signed certificate authority (CA) that will be signing the client/proxy certs. Will have passphrase `testcapassphrase` |
| `testaggregator.crt` | Certificate for the client certificate registered to a testing "aggregator" |
| `testaggregator.key` | Private Key for the client certificate registered to a testing "aggregator". Will have passphrase `testclientpassphrase` |
| `testaggregator.p12` | PKCS#12/PFX, a convenient combination of the `testaggregator.crt` and `testaggregator.key`. Will have passphrase `testclientpassphrase` |
 `testdevice.crt` | Certificate for the client certificate registered to a testing non-aggregator "device" |
| `testdevice.key` | Private Key for the client certificate registered to a testing non-aggregator "device". Will have passphrase `testclientpassphrase` |
| `testdevice.p12` | PKCS#12/PFX, a convenient combination of the `testdevice.crt` and `testdevice.key`. Will have passphrase `testclientpassphrase` |

The client certificates described in the table above are signed by the test CA and can be used against the nginx instance exposed on port 8443.

You are welcome to sign additional certificates using the "test ca", but please note that authorising the certificate as an 'aggregator' will require it to be registered in the `envoy-db` database. To do this, the certificate must be first registered to `public.certificate` (using its lFDI) and linked to `public.aggregator` via the linking table `public.aggregator_certificate_assignment`. A more detailed procedure will be provided in future documentation.

## Making your first request

The easiest way to validate that the example services have started is by issuing a HTTPS request to localhost:8443/dcap

```
curl --cacert ./tls-termination/test_certs/testca.crt --cert ./tls-termination/test_certs/testdevice.p12:testclientpassphrase --cert-type p12 https://localhost:8443/dcap
```

That should generate a response like this:
```
<DeviceCapability xmlns="urn:ieee:std:2030.5:ns" xmlns:csipaus="https://csipaus.org/ns" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" href="/dcap"><TimeLink href="/tm"/><EndDeviceListLink href="/edev" all="0"/><MirrorUsagePointListLink href="/mup" all="0"/></DeviceCapability>
```

## Connecting with Postman

In the root repository directory under `postman/` you'll find Postman collections for both envoy and envoy-admin.

You'll need to import them and then do the following:
1. File -> Settings -> Certificates -> Client Certificates -> Add Certificate
    * Set the certificate host to `https://localhost:8443`
    * Set the PFX file to `testdevice.p12` (see table above for passphrase and other info)
2. envoy collection -> Variables
    * Set HOST to `localhost:8443`


## Initial Database Content

When first loaded, the database will be loaded with the bare minimum to run envoy and connect. Only a test aggregator and non-aggregator devices with the provided client certificates will be loaded.

This will be enough to run `EndDevice` registration workflows.

In order to receive dynamic operating envelopes / prices / etc, they will need to be injected via the admin-server. Please see the example Postman collections for how to do that.
