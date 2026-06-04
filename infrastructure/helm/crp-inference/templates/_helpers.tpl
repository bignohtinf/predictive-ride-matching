{{- define "crp-inference.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "crp-inference.fullname" -}}
{{- printf "%s" (include "crp-inference.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "crp-inference.labels" -}}
app.kubernetes.io/name: {{ include "crp-inference.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}
