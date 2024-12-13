FROM nginx:bookworm

ARG HOST_UID
ARG HOST_GID
ARG TEST_CA_PASSPHRASE
ARG TEST_CLIENT_PASSPHRASE

RUN usermod -u $HOST_UID www-data && \
    groupmod -g $HOST_GID www-data

COPY --chown=www-data:www-data ./nginx.conf /etc/nginx/nginx.conf
COPY --chown=www-data:www-data --chmod=770 ./entrypoint/* /

USER www-data
RUN sh /tls-setup.sh

USER root
CMD ["sh", "/entrypoint.sh"]
