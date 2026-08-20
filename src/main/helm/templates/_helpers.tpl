{{- define "name" -}}
{{- if .Values.nameOverride -}}{{- .Values.nameOverride -}}
{{- else -}}{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "labels" -}}
{{- if .Values.labels -}}
{{- toYaml .Values.labels -}}
{{- end -}}
{{- end -}}

{{- define "annotations" -}}
{{- if .Values.annotations -}}
{{- toYaml .Values.annotations -}}
{{- end -}}
{{- end -}}

{{- define "configsecretLabels" -}}
{{- $labels := merge (.Values.labels | default dict) (.Values.config.labels | default dict) -}}
{{- if $labels -}}
{{- toYaml $labels }}
{{- else -}}
{}
{{- end -}}
{{- end -}}

{{- define "serviceName" -}}
{{- if .Values.service.nameOverride -}}
  {{ .Values.service.nameOverride }}
{{- else -}}
  {{- include "name" . -}}
{{- end -}}
{{- end -}}

{{- define "certificateCommonName" -}}
{{- if .Values.tls.certManager.certificate.commonNameOverride -}}
  {{- .Values.tls.certManager.certificate.commonNameOverride -}}
{{- else -}}
  {{- include "serviceName" . -}}
{{- end -}}
{{- end -}}

{{- define "healthcheck" -}}
httpGet:
  path: /health
  {{- if .Values.pod.portOverride }}
  port: {{ .Values.pod.portOverride.name }}
  {{- else }}
  port: {{ ternary "https" "http" .Values.tls.enabled }}
  {{- end }}
  scheme: {{ ternary "HTTPS" "HTTP" .Values.tls.enabled }}
initialDelaySeconds: {{ .Values.pod.healthcheck.initialDelaySeconds }}
periodSeconds: {{ .Values.pod.healthcheck.periodSeconds }}
timeoutSeconds: {{ .Values.pod.healthcheck.timeoutSeconds }}
successThreshold: {{ .Values.pod.healthcheck.successThreshold }}
failureThreshold: {{ .Values.pod.healthcheck.failureThreshold }}
{{- end -}}
