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
