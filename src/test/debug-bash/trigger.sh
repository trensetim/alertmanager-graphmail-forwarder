#!/bin/bash

# must be run from project root
source .env

# thanks to https://gist.github.com/mobeigi/5a96f326bc06c7d6f283ecb7cb083f2b
curl -X POST -v -H "Content-Type: application/json" -d '{
  "receiver": "webhook",
  "status": "firing",
  "alerts": [
    {
      "status": "firing",
      "labels": {
        "alertname": "Test",
        "instance": "localhost:9090",
        "job": "prometheus24"
      },
      "annotations": {
        "description": "some description",
        "abc": "def",
        "summary": "test alert"
      },
      "startsAt": "2018-08-03T09:52:26.739266876+02:00",
      "endsAt": "0001-01-01T00:00:00Z",
      "generatorURL": "example.com",
      "fingerprint": "abc123"
    }
  ],
  "groupLabels": {
    "alertname": "Test",
    "job": "prometheus24"
  },
  "commonLabels": {
    "alertname": "Test",
    "instance": "localhost:9090",
    "job": "prometheus24"
  },
  "commonAnnotations": {
    "description": "some description"
  },
  "externalURL": "http://example.com:9093",
  "version": "4",
  "groupKey": "group1"
}' \
    -H "Authorization: Bearer $AUTH_TOKEN" \
    --insecure \
    "https://localhost:$LISTEN_PORT/alert"
