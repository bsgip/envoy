#!/bin/bash
set -e

exec "$@"

cp -ar  /tmp/certs/* /test_certs/

nginx -g 'daemon off;'