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