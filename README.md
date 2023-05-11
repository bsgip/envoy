# envoy
2030.5 / CSIP-AUS utility server implementation

## Project structure

Top level directories define fastapi apps that use a common auth model

* `requirements/`: holds requirement files for specific environments
* `src/envoy/`: root package directory
* `src/envoy/admin/`: Used for internal API endpoints for administering the server/injecting calculated entities
* `src/envoy/server/`: primary implementation of the public API's - eg 2030.5 etc 
* `tests/`: root tests directory

docstrings on `__init__.py` should describe the structure in greater detail

## Dependencies/Requirements

`requirements.txt` contains all the dependencies required to run Envoy. 

The `requirements/` directory contains seperate `requirements.XXX.txt` files for specific purposes beyond the runtime dependencies.

The latest stable/frozen set of requirements can be found in `requirements/requirements.prod.txt`. This file can be regenerated (from a clean virtual environment) using `pip freeze > requirements/requirements.prod.txt`

## Contributing

The following linters/checkers are run on every PR. It's highly recommended to have these running as part of your development setup. `vscode` has plugins to make this easy or run the below manually

`pip install -r requirements/requirements.dev.txt`

| **Tool** | **Running** | **Purpose** |
| -------- | ----------- | ----------- |
| `bandit` | `bandit .` | checking for common security issues |
| `black` | `black --check .` | validating code style/formatting |
| `mypy` | `mypy src/` | enforce type hints and other associated linting - excluding tests |
| `pytest` | `pytest` | Runs all tests (more info below) |


## Running Locally

### Locally Hosted

To run Envoy locally as a development environment you'll need to setup a local postgresql database and python. This guide will assume that you have python 3.10+ and postgresql 14+ installed.

1. Install dependencies for main server + tests

`pip install -r requirements.txt`
`pip install -r requirements/requirements.testing.txt`

2. (optional) Install development requirements

`pip install -r requirements/requirements.dev.txt`

3. Double check tests are running

`pytest`

4. Create an "envoy" database

```
sudo -u postgres psql
postgres=# create database envoydb;
postgres=# create user envoyuser with encrypted password 'mypass';
postgres=# grant all privileges on database envoydb to envoyuser;
```

5. Create `.env` file

Envoy is is dependent on a number of environment variables listed in the table below.

| Environment Variable | Description |
| --- | --- |
| `DATABASE_URL` | The postgres database connection string eg: `postgresql+asyncpg://envoyuser:mypass@localhost:5432/envoydb` (NOTE - `asyncpg` is required for fastapi) |

We recommend adding these to a `.env` file in the root directory so that they are accessible by both fastapi and docker.

6. Install local copy

`pip install -e ./`

7. Apply alembic migrations to the database schema

`cd src/envoy/server/`

If there are no migrations in `server/alembic/versions` - first run `alembic revision --autogenerate -m "Init"`

`alembic upgrade head`

8. You may want to put some aggregators along with their associated lFDIs into the database created in Step 3. We can use the base config from the testing environment for this purpose:

`sudo -u postgres psql -d envoydb -a -f tests/data/sql/base_config.sql`

The Postman collection in postman/envoy.postman_collection.json uses certificate 1 (`tests/data/certificates/certificate1.py`)
 to make it requests and will require the database to be populated with this base config.

9. Start server

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

