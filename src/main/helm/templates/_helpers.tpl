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

{{- define "healthcheck" -}}
httpGet:
  path: /health
  port: http
  scheme: HTTP
initialDelaySeconds: 1
{{- end -}}
