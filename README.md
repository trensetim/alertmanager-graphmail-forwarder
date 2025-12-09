Webhook-Integration that forwards [Alertmanager](https://github.com/prometheus/alertmanager) notifications to mails via [Microsoft Graph SendMail API](https://learn.microsoft.com/en-us/graph/api/user-sendmail).

Since Microsoft disabled SMTP BasicAuth in favor of OAuth2-authentication for SMTP, the built-in smtp target of alertmanager does not work natively with MS Exchange mail servers.
This forwarder bridges that gap by receiving notifications via [WebHooks](https://prometheus.io/docs/alerting/latest/configuration/#webhook_config) and forwarding them to email receivers via [MS Graph API](https://en.wikipedia.org/wiki/Microsoft_Graph).

```mermaid
flowchart LR
    prom@{img: "https://upload.wikimedia.org/wikipedia/commons/3/38/Prometheus_software_logo.svg", label: "Prometheus", w: 60, h: 60, constraint: "on", cc: "Apache2"}
    am@{img: "https://upload.wikimedia.org/wikipedia/commons/3/38/Prometheus_software_logo.svg", label: "Alertmanager", w: 60, h: 60, constraint: "on", cc: "Apache2"}
    this[Alertmanager GraphMail Forwarder]
    ms@{img: "https://upload.wikimedia.org/wikipedia/commons/e/ea/Microsoft_Exchange_%282019-present%29.svg", label: "Microsoft Exchange", constraint: "on", w: 60, h: 60, cc: "public domain"}
    user@{img: "https://upload.wikimedia.org/wikipedia/commons/5/59/User-avatar.svg", label: "Receiver", constraint: "on", w: 60, h: 60, cc: "public domain"}

    prom-- alerts -->am
    am-- notification / webhook -->this
    this-- Graph SendMail API -->ms
    ms-- Mail -->user

%% Sources and Licenses are stated in the object declarations.
```

## Contributing

To get started, initialize a python venv by
  - `python -m venv .`
  - `. bin/activate`
  - `pip install -r src/build/python/requirements.txt`

## Configuration

The application is configured via environment variables.

| Variable       | Description           |
|----------------|-----------------------|
| FROM           | Sender E-Mail Address |
| TO             | Recipient E-Mail Address List (comma-separated, no spaces) |
| CLIENT_ID      | OAuth2 EntraID client id of this application's registration |
| CLIENT_SECRET  | OAuth2 EntraID client secret of this application's registration |
| TENANT_ID      | UUID of the EntraID tenant of the organization hosting the Exchange Mail Server |
| AUTH_TOKEN     | Secret for the HTTP Authorization Bearer header, according to [RFC6750](https://datatracker.ietf.org/doc/html/rfc6750) |
| LISTEN_ADDRESS | [default = 0.0.0.0] Bind to local address |
| LISTEN_PORT    | [default = 8080] Bind to local tcp port (for serving the http webhook receiver) |
| TLS_CERT_PATH, TLS_KEY_PATH | [default = no tls] Filesystem paths to an X509 certificate in PEM format (for serving the http webhook receiver). The container will automatically pick up on a mounted `/app/tls/crt.pem` and `/app/tls/key.pem` combination. |
| HTTP_TIMEOUT_SECONDS | default=10 Used during access to MS Graph API |

For the sensitive values (`CLIENT_ID`, `CLIENT_SECRET`, `TENANT_ID`, `AUTH_TOKEN`), if they start with a literal `/` (forward-slash), the value is interpreted as a filesystem path and the actual secret value is read from that file.
The file content will get whitespace-trimmed and UTF-8 decoded.

## Getting Started

For running locally, do

```bash
PORT="8080"
CLIENT_SECRET="$(dd if=/dev/random bs=4K count=1 2>/dev/null | sha256sum | head -c 32)"
CLIENT_SECRET_PATH="/app/client_secret"
echo -n "$CLIENT_SECRET" > client_secret
TENANT_ID="$(uuidgen -r)"

# for debugging with TLS. (Omit the relevant mounts for plain-http mode)
openssl req -x509 -newkey rsa:4096 -nodes -out crt.pem -keyout key.pem -days 365

docker run --rm -it -p $PORT:$PORT \
    -e "HTTP_PORT=$PORT" \
    -e "TO=someone@example.com,another@example.com" \
    -e "FROM=prometheus@example.com" \
    -e "CLIENT_ID=prometheus" \
    -e "TENANT_ID=$TENANT_ID" \
    -e "CLIENT_SECRET=$CLIENT_SECRET_PATH" \
    -v "$(pwd)/client_secret:${CLIENT_SECRET_PATH}:ro" \
    -e "AUTH_TOKEN=DISABLED" \
    -v "$(pwd)/crt.pem:/app/tls/crt.pem:ro" \
    -v "$(pwd)/key.pem:/app/tls/key.pem:ro" \
    docker-registry.timtrense.com/tim/alertmanager-graphmail-forwarder:latest
```
