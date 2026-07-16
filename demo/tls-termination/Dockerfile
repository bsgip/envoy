FROM nginx:bookworm

ARG HOST_UID
ARG HOST_GID

RUN if [ -n "$HOST_UID" ] && [ -n "$HOST_GID" ]; then \
        groupmod -o -g "$HOST_GID" www-data && \
        usermod -u "$HOST_UID" www-data; \
    fi

COPY --chown=www-data:www-data ./nginx.conf /etc/nginx/nginx.conf
COPY --chown=www-data:www-data --chmod=770 ./entrypoint/* /

USER www-data
RUN sh /tls-setup.sh

USER root
CMD ["sh", "/entrypoint.sh"]
