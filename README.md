# envoy
2030.5 / CSIP-AUS utility server implementation

## Project structure

Top level directories define fastapi apps that use a common auth model

* `requirements/`: holds requirement files for specific environments
* `src/envoy/`: root package directory
* `src/envoy/admin/`: Used for internal API endpoints for administering the server/injecting calculated entities
* `src/envoy/server/`: primary implementation of the public API's - eg 2030.5 etc 
* `src/envoy/notification` : Used for handling all notification server tasks/workers for supporting 2030.5 pub/sub
* `tests/`: root tests directory

docstrings on `__init__.py` should describe the structure in greater detail

## Settings

Envoy has a number of configuration settings that turn on/off optional functionality. It should run fine out of the box but the below table will detail the additional options.

Typically settings are set by setting an environment variable with the same name (case insensitive).


| **Setting** | **Type** | **Purpose** |
| ----------- | -------- | ----------- |
| `database_url` | `string` | The core `PostgresDsn` for connecting to the envoy database. eg `postgresql+asyncpg://envoyuser:mypass@localhost:5432/envoydb` |
| `cert_header` | `string` | The name of the HTTP header that API endpoints will look for to validate a client. This should be set by the TLS termination point and can contain either a full client certificate in PEM format or the sha256 fingerprint of that certificate. defaults to "x-forwarded-client-cert" |
| `default_timezone` | `string` | The timezone name that will be used as the default for new sites registered in band (defaults to "Australia/Brisbane") |
| `enable_notifications` | `bool` | Whether notifications for active subscriptions will be generated. Notifications will either be handled in a local threadpool (if `rabbit_mq_broker_url` is None or via a dedicated task_iq worker connected to the same `rabbit_mq_broker_url` instance) |
| `rabbit_mq_broker_url` | `string` | URL to a rabbit MQ instance that will handle notifications. Eg `amqp://user:password@localhost:5672`. Will require a worker servicing this instance |
| `azure_ad_tenant_id` | `string` | The Azure AD tenant id that envoy is deployed under (see Azure Active Directory Support below) |
| `azure_ad_client_id` | `string` | The Azure AD client id that identifies the VM envoy is deployed under (see Azure Active Directory Support below) |
| `azure_ad_valid_issuer` | `string` | The Azure AD issuer that will be generating tokens for the current tenant (see Azure Active Directory Support below) |
| `azure_ad_db_resource_id` | `string` | If set (with the other Azure AD options) - replaces the db connection password dynamically with a token minted from the tenant token service for this resource id. The token ID should match the resource ID of a managed database service. This token will be rotated as it expires. |
| `azure_ad_db_refresh_secs` | `int` | If `azure_ad_db_resource_id` is set - the value of this variable will be the rate at which tokens are manually refreshed (in seconds) |
| `href_prefix` | `string` | Used for when the server is exposed externally under a path prefix. The value of this variable will be prefixed to all returned `href` elements |
| `default_doe_import_active_watts` | `float` | If set - the DefaultDERControl endpoint will be activated with the DOE extensions for import being set to this value (requires `default_doe_export_active_watts`)|
| `default_doe_export_active_watts` | `float` | If set - the DefaultDERControl endpoint will be activated with the DOE extensions for export being set to this value (requires `default_doe_import_active_watts`)|

### Azure Active Directory Support + Managed Identity

Envoy can be run in a Azure tenant on a VM with a managed identity where this identity can be used to validate incoming/outgoing connections in addition to the normal 2030.5 cert auth.

Enabling this auth will ensure that all incoming requests must include an `Authorization: bearer <AzureADToken>` header in addition to the "normal" auth headers. This token will be validated against the configured Azure AD tenant/client/issuer.

To enable - set the config for `azure_ad_tenant_id`/`azure_ad_client_id`/`azure_ad_valid_issuer`

## Dependencies/Requirements

`pip install .` will install the basic dependencies to run Envoy

`pip install .[dev]` will install the optional development dependencies (eg code linters)

`pip install .[test]` will install the optional testing dependencies (eg pytest)

## Contributing

The following linters/checkers are run on every PR. It's highly recommended to have these running as part of your development setup. `vscode` has plugins to make this easy or run the below manually

`pip install .[dev]`

| **Tool** | **Running** | **Purpose** |
| -------- | ----------- | ----------- |
| `bandit` | `bandit .` | checking for common security issues |
| `black` | `black --check .` | validating code style/formatting |
| `mypy` | `mypy src/` | enforce type hints and other associated linting - excluding tests |
| `pytest` | `pytest` | Runs all tests (more info below) |


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

`pip install .[test]`

2. (optional) Install development requirements

`pip install .[dev]`

3. Double check tests are running

`pytest`

4. Create an "envoy" database

```
sudo -u postgres psql
postgres=# create database envoydb;
postgres=# create user envoyuser with encrypted password 'mypass';
postgres=# grant all privileges on database envoydb to envoyuser;
```

Note: for postgres>=15, create privileges on the public schema are no longer created by default. 
To enable table creation with the envoyuser, grant ownership of the database (local development only)
```
postgres=# ALTER DATABASE envoydb TO OWNER envoyuser;
```

5. Create `.env` file

Envoy is is dependent on a number of environment variables listed in the table below.

| Environment Variable | Description |
| --- | --- |
| `DATABASE_URL` | The postgres database connection string eg: `postgresql+asyncpg://envoyuser:mypass@localhost:5432/envoydb` (NOTE - `asyncpg` is required for fastapi) |

We recommend adding these to a `.env` file in the root directory so that they are accessible by both fastapi and docker.

6. Install local copy

`pip install -e .`

7. Apply alembic migrations to the database schema

`cd src/envoy/server/`

If there are no migrations in `server/alembic/versions` - first run `alembic revision --autogenerate -m "Init"`

`alembic upgrade head`

8. You may want to put some aggregators along with their associated lFDIs into the database created in Step 3. We can use the base config from the testing environment for this purpose:

`sudo -u postgres psql -d envoydb -a -f tests/data/sql/base_config.sql`

The Postman collection in postman/envoy.postman_collection.json uses certificate 1 (`tests/data/certificates/certificate1.py`)
 to make it requests and will require the database to be populated with this base config.

9. Start notification server worker

The notification server will require workers to handle executing the async tasks. This is handled by taskiq and a worker
can be initialised with: 

`taskiq worker envoy.notification.main:broker envoy.notification.task`

10. Start server

`python server/main.py`

### Docker Hosted

TODO: Depending on Dockerfile

### Docker Hosted - Running envoy

#### Setup

1. Create this `docker-compose.yaml` file in the project root:

```yaml
```

You may need to check whether the directory `/var/lib/postgresql/data/` which is where the database is persisted.

2. Bring up the database server

```shell
docker compose up -d
```

3. Connect to the server

```shell
docker exec -it envoy-timescaledb-1 psql -U postgres
```

You will probably need to replace the name of the container (use `docker ps -a` to find the name of your running container).

4. At the psql prompt running the following commands to set up the database.

```
create database envoydb;
create user envoyuser with encrypted password 'mypass';
grant all privileges on database envoydb to envoyuser;
exit
```

5. Update the `DATABASE_URL` in the `.env` to use this database (**note** the use of port 5433 to prevent a clash with any locally installed postgres server)

DATABASE_URL=postgresql+asyncpg://envoyuser:mypass@localhost:5433/envoydb

6. Generate and apply the migrations

```
cd src/envoy/server
ln -s ../../../.env
alembic revision --autogenerate -m "Init"
alembic upgrade head
```


### Docker Hosted - Database only set up to allow running the test suite

#### Setup

1. Create this `docker-compose.testing.yaml` file in the project root:

```yaml
version: '3'

services:
  testdb:
    image: timescale/timescaledb:latest-pg14
    environment:
      # 'POSTGRES_PASSWORD' needs to match the password used in tests/conftest.py
      - POSTGRES_PASSWORD=adminpass
      # If the mapping of the /etc/localtime fails (see volumes section) then comment out that line and
      # uncomment the following two lines (making sure to set the timezone to the same as your host system).
      # - TZ=Australia/Brisbane
      # - PGTZ=Australia/Brisbane
    ports:
      # Expose postgresql on port 5433 to prevent a clash with any local installation of postgresql server (default=5432).
      - 5433:5432
    volumes:
      # Map in the localtime. This results in the timezone of postgresql being set to the same as host system.
      - "/etc/localtime:/etc/localtime:ro"

# Create a new network separate than the one created for docker.compose.yaml
networks:
  default:
    name: envoy-testing
```

Since the test suite brings up the database each time there is no docker volume for persisting the database.

#### Running the tests

1. Bring up the database server to make sure it available to the test suite

```shell
docker compose -f docker-compose.testing.yaml up -d
```

2. Run the test suite

```
TEST_WITH_DOCKER=1 pytest
```

The environment variable `TEST_WITH_DOCKER` forces the pytest to use postgresql server in the docker container rather
than any local postgresql server.

