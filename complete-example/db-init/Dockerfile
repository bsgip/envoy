FROM envoy:latest

WORKDIR /app/src/envoy/server/

COPY --chmod=700 ./entrypoint.sh /entrypoint.sh
COPY  ./init_db.py ./init_db.py

CMD [ "/entrypoint.sh" ]
