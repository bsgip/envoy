# envoy

A fully open source, CSIP-Aus compliant utility server initially developed by the [Battery Storage and Grid Integration Program](https://bsgip.com/) at the [Australian National University](https://www.anu.edu.au/). Implements the following standards:

* [2030.5: Smart Energy Profile (2030.5-2018)](https://standards.ieee.org/ieee/2030.5/5897/)
* [CSIP: Common Smart Inverter Profile](https://sunspec.org/2030-5-csip/)
* [CSIP-Aus: Common Smart Inverter Profile (Australia)](https://csipaus.org/)

It's a docker containerised fastapi server, backed by postgresql for interacting with "smart devices" implementing the CSIP-AUS standard.

All client model definitions for this server can be found in [envoy-schema](https://github.com/bsgip/envoy-schema) project (a dependency of envoy)

# Demo server (example)

envoy has a full demo server for quickly evaluating its capabilities. See the [demo/](demo/README.md) directory for more info

# Development

To install envoy for local development, clone this repository and then run:

`pip install -e .[dev,test]`

To ensure everything is setup correctly, tests can be run with:

`pytest`

envoy uses the following linting/formatting tools:
* [black](https://pypi.org/project/black/)
* [flake8](https://pypi.org/project/flake8/)
* [mypy](https://pypi.org/project/mypy/)
* [bandit](https://pypi.org/project/bandit/)

Contributions via a pull request are welcome but will be validated using the above tools.

## Project structure

Top level directories define multiple apps that use a common codebase/shared models.

* `demo/`: A fully containerised demonstration of all services in this project
* `src/envoy/`: root package directory
* `src/envoy/admin/`: Used for internal API endpoints for administering the server/injecting calculated entities
* `src/envoy/server/`: primary implementation of the public API's - eg 2030.5 etc 
* `src/envoy/notification` : Used for handling all notification server tasks/workers for supporting 2030.5 pub/sub
* `tests/`: root tests directory

docstrings on `__init__.py` should describe the structure in greater detail

## Settings

Envoy has a number of configuration settings that turn on/off optional functionality. It should run fine out of the box but the below table will detail the additional options.

Typically settings are set by setting an environment variable with the same name (case insensitive).

**Common Settings**

| **Setting** | **Type** | **Purpose** |
| ----------- | -------- | ----------- |
| `database_url` | `string` | The core `PostgresDsn` for connecting to the envoy database. eg `postgresql+asyncpg://envoyuser:mypass@localhost:5432/envoydb` |
| `default_timezone` | `string` | The timezone name that will be used as the default for new sites registered in band (defaults to "Australia/Brisbane") |
| `enable_notifications` | `bool` | Whether notifications for active subscriptions will be generated. Notifications will either be handled in a local threadpool (if `rabbit_mq_broker_url` is None or via a dedicated task_iq worker connected to the same `rabbit_mq_broker_url` instance) |
| `rabbit_mq_broker_url` | `string` | URL to a rabbit MQ instance that will handle notifications. Eg `amqp://user:password@localhost:5672`. Will require a worker servicing this instance |
| `azure_ad_tenant_id` | `string` | The Azure AD tenant id that envoy is deployed under (see Azure Active Directory Support below) |
| `azure_ad_client_id` | `string` | The Azure AD client id that identifies the VM envoy is deployed under (see Azure Active Directory Support below) |
| `azure_ad_valid_issuer` | `string` | The Azure AD issuer that will be generating tokens for the current tenant (see Azure Active Directory Support below) |
| `azure_ad_db_resource_id` | `string` | If set (with the other Azure AD options) - replaces the db connection password dynamically with a token minted from the tenant token service for this resource id. The token ID should match the resource ID of a managed database service. This token will be rotated as it expires. |
| `azure_ad_db_refresh_secs` | `int` | If `azure_ad_db_resource_id` is set - the value of this variable will be the rate at which tokens are manually refreshed (in seconds) |
| `href_prefix` | `string` | Used for when the server is exposed externally under a path prefix. The value of this variable will be prefixed to all returned `href` elements |
| `iana_pen` | `int` | Defaults to 0. The Internet Assigned Numbers Authority - Private Enterprise Number of the organisation hosting this instance. This value will be used in all encoded MRIDs as per sep2 specifications. |
| `sqlalchemy_engine_arguments` | `str` | A JSON encoded dictionary of additional parameters to pass to the SQL Alchemy `create_engine` function. Please see the [SQL Alchemy](https://docs.sqlalchemy.org/en/20/core/engines.html#sqlalchemy.create_engine) docs for specifics.  Example: `{"pool_size":10, "max_overflow":15}`. Please note that `pool_recycle` will be overridden if `azure_ad_db_refresh_secs` is set |

**Additional Utility Server Settings (server)**

| **Setting** | **Type** | **Purpose** |
| ----------- | -------- | ----------- |
| `cert_header` | `string` | The name of the HTTP header that API endpoints will look for to validate a client. This should be set by the TLS termination point and can contain either a full client certificate in PEM format or the sha256 fingerprint of that certificate. defaults to "x-forwarded-client-cert" |
| `default_doe_import_active_watts` | `float` | If set - the DefaultDERControl endpoint will be activated with the DOE extensions for import being set to this value (requires `default_doe_export_active_watts`)|
| `default_doe_export_active_watts` | `float` | If set - the DefaultDERControl endpoint will be activated with the DOE extensions for export being set to this value (requires `default_doe_import_active_watts`)|
| `allow_device_registration` | `bool` | If True - the registration workflows that enable unrecognised certs to generate/manage a single EndDevice (tied to that cert) will be enabled. Otherwise any cert will need to be registered out of band and assigned to an aggregator before connections can be made. Defaults to False|


**Additional Admin Server Settings (admin)**

| **Setting** | **Type** | **Purpose** |
| ----------- | -------- | ----------- |
| `admin_username` | `string` | The username for HTTP BASIC credentials that will grant "admin" access to all endpoints. Should only be used for tight integrations with local calculation engines |
| `admin_password` | `string` | The password for HTTP BASIC credentials that pairs with `admin_username` |
| `read_only_user` | `string` | The username for HTTP BASIC credentials that will grant "read only" access to all GET endpoints. |
| `read_only_keys` | `list[string]` | Various passwords for HTTP BASIC credentials that each pair with `read_only_username`. Multiple entries should be encoded as a JSON list eg: `READ_ONLY_KEYS='"Password1", "Password2"]'` |

### Azure Active Directory Support + Managed Identity

Envoy can be run in a Azure tenant on a VM with a managed identity where this identity can be used to validate incoming/outgoing connections in addition to the normal 2030.5 cert auth.

Enabling this auth will ensure that all incoming requests must include an `Authorization: bearer <AzureADToken>` header in addition to the "normal" auth headers. This token will be validated against the configured Azure AD tenant/client/issuer.

To enable - set the config for `azure_ad_tenant_id`/`azure_ad_client_id`/`azure_ad_valid_issuer`

## Updating database schema

If updating any of the crud models - you will need to update the alembic migrations:

1. Ensure any new models are being imported at `src/envoy/server/model/__init__.py` (this is where the alembic `env.py` imports all models)
2. Create updated migration:

```
cd src/envoy/server
alembic revision --autogenerate -m "MY_SUMMARY_OF_CHANGES"
```

3. Check the newly created migration file in `src/envoy/server/alembic/versions` (make sure it has what you've changed)


## Running Locally

### Locally Hosted

To run Envoy locally as a development environment you'll need to setup a local postgresql database and python. This guide will assume that you have python 3.10+ and postgresql 14+ installed.

1. Install dependencies for main server + tests

`pip install -e .[test,dev]`

2. Create an "envoy" database

```
sudo -u postgres psql
postgres=# create database envoydb;
postgres=# create user envoyuser with encrypted password 'mypass';
postgres=# grant all privileges on database envoydb to envoyuser;
```

Note: for postgres>=15, create privileges on the public schema are no longer created by default. 
To enable table creation with the envoyuser, grant ownership of the database (local development only)
```
postgres=# ALTER DATABASE envoydb OWNER TO envoyuser;
```

3. Create `.env` file

Envoy is is dependent on a number of environment variables (see the section on settings above). For a minimal local installation, you'll want to set the following:

| Environment Variable | Description |
| --- | --- |
| `DATABASE_URL` | The postgres database connection string eg: `postgresql+asyncpg://envoyuser:mypass@localhost:5432/envoydb` (NOTE - `asyncpg` is required for fastapi) |
| `ADMIN_USERNAME` | Username for HTTP BASIC auth on the admin server eg: `testuser` |
| `ADMIN_PASSWORD` | Password for HTTP BASIC auth on the admin server eg: `testpassword` |

We recommend adding these to a `.env` file in the root directory so that they are accessible by both fastapi and docker.

4. Apply alembic migrations to the database schema

```
ln -s $PWD/.env $PWD/src/envoy/server/.env
cd src/envoy/server/
alembic upgrade head
cd -
```

5. You may want to put some aggregators along with their associated lFDIs into the database created in Step 3. We can use the base config from the testing environment for this purpose:

`sudo -u postgres psql -d envoydb -a -f tests/data/sql/base_config.sql`

The Postman collection in postman/envoy.postman_collection.json uses certificate 1 (`tests/data/certificates/certificate1.py`) to make its requests and will require the database to be populated with this base config.

6. (Optional) Start notification server worker

The notification server will require workers to handle executing the async tasks. This is handled by taskiq and a worker
can be initialised with: 

`taskiq worker envoy.notification.main:broker envoy.notification.task`

7. Start server

`uvicorn envoy.server.main:app --host 0.0.0.0 --reload`
            
