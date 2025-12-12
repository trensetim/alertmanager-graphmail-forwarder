FROM python:3-alpine
WORKDIR /app
COPY --chown=1000:1000 src/build/python/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    apk add curl inotify-tools
COPY --chown=1000:1000 src/main/python/ /app
COPY --chown=1000:1000 src/main/docker/ /app
STOPSIGNAL SIGTERM
USER 1000:1000
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 CMD [ "/app/healthcheck.sh" ]
ENTRYPOINT [ "/app/entrypoint.sh" ]
