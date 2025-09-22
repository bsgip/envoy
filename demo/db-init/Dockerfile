FROM envoy:latest

WORKDIR /app/src/envoy/server/

ENV AGG_CERT_PATH="/test_certs/testaggregator.crt"

COPY --chmod=700 ./entrypoint.sh /entrypoint.sh
COPY  ./init_db.py ./init_db.py

CMD [ "/entrypoint.sh" ]
