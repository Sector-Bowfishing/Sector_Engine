#!/usr/bin/env python3
"""Idempotent Cloud Monitoring setup for sector-engine: channel, uptime checks,
log-based metrics, alert policies. Re-running updates nothing that already exists
(matched by display name / metric name) and creates what's missing."""
import json, subprocess, sys, urllib.request, urllib.error

PROJECT = "sector-9393c"
SERVICE = "sector-engine"
HOST = "sector-engine-e43utajroa-uc.a.run.app"
EMAIL = "mgcather07@gmail.com"
TOKEN = subprocess.check_output(["gcloud", "auth", "print-access-token"], text=True).strip()
MON = f"https://monitoring.googleapis.com/v3/projects/{PROJECT}"
LOG = f"https://logging.googleapis.com/v2/projects/{PROJECT}"


def call(method, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json",
        "x-goog-user-project": PROJECT})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{method} {url} -> {e.code}: {e.read().decode()[:800]}")


def list_all(url, key):
    out, token = [], None
    while True:
        page = call("GET", url + (f"?pageToken={token}" if token else ""))
        out += page.get(key, [])
        token = page.get("nextPageToken")
        if not token:
            return out


# ── Notification channel ─────────────────────────────────────────────────────
channels = list_all(f"{MON}/notificationChannels", "notificationChannels")
channel = next((c for c in channels if c.get("type") == "email"
                and c.get("labels", {}).get("email_address") == EMAIL), None)
if not channel:
    channel = call("POST", f"{MON}/notificationChannels", {
        "type": "email", "displayName": f"Sector engine alerts ({EMAIL})",
        "labels": {"email_address": EMAIL}})
    print("created channel", channel["name"])
else:
    print("channel exists", channel["name"])
CH = channel["name"]

# ── Uptime checks ────────────────────────────────────────────────────────────
uptimes = {u["displayName"]: u for u in list_all(f"{MON}/uptimeCheckConfigs", "uptimeCheckConfigs")}
def uptime(name, path, period, timeout, content):
    if name in uptimes:
        print("uptime exists", name); return uptimes[name]
    u = call("POST", f"{MON}/uptimeCheckConfigs", {
        "displayName": name,
        "monitoredResource": {"type": "uptime_url", "labels": {"project_id": PROJECT, "host": HOST}},
        "httpCheck": {"path": path, "port": 443, "useSsl": True, "validateSsl": True,
                      "requestMethod": "GET",
                      "acceptedResponseStatusCodes": [{"statusValue": 200}]},
        "period": period, "timeout": timeout,
        "contentMatchers": [{"content": content, "matcher": "CONTAINS_STRING"}],
        "selectedRegions": ["USA_IOWA", "USA_OREGON", "USA_VIRGINIA"],
    })
    print("created uptime", name); return u
up_health = uptime("sector-engine /health", "/health", "60s", "10s", "ok")
# A real render that must contain weather — catches "up but not scoring" (a
# weather outage returns 503; a fabricated render would lack the weather object).
up_deep = uptime("sector-engine /conditions (Guntersville)", "/conditions?lat=34.35&lon=-86.30",
                 "900s", "60s", '"weather":{')

# ── Log-based metrics ────────────────────────────────────────────────────────
metrics = {m["name"]: m for m in list_all(f"{LOG}/metrics", "metrics")}
BASE = f'resource.type="cloud_run_revision" AND resource.labels.service_name="{SERVICE}"'
def log_metric(name, desc, filt):
    if name in metrics:
        print("metric exists", name); return
    call("POST", f"{LOG}/metrics", {
        "name": name, "description": desc, "filter": f"{BASE} AND ({filt})",
        "metricDescriptor": {"metricKind": "DELTA", "valueType": "INT64", "unit": "1"}})
    print("created metric", name)
log_metric("engine_container_crash", "Engine process crashed (signal) or container terminated",
           'textPayload:"Uncaught signal" OR textPayload:"Container terminated on signal"')
log_metric("engine_render_unavailable", "Render refused: no weather to score honestly (503)",
           'jsonPayload.message="render unavailable: no weather"')
log_metric("engine_upstream_failure", "An upstream fetch failed (transport, deadline, 403/429/5xx)",
           'jsonPayload.message="upstream request failed" OR jsonPayload.message="upstream error status"')
log_metric("engine_remote_config_rejected", "Remote Config payload rejected by validation",
           'jsonPayload.message="remote config rejected; keeping last good config"')

# ── Alert policies ───────────────────────────────────────────────────────────
policies = {p["displayName"]: p for p in list_all(f"{MON}/alertPolicies", "alertPolicies")}
def policy(name, doc, condition):
    if name in policies:
        print("policy exists", name); return
    call("POST", f"{MON}/alertPolicies", {
        "displayName": name, "combiner": "OR", "enabled": True,
        "notificationChannels": [CH],
        "documentation": {"content": doc, "mimeType": "text/markdown"},
        "alertStrategy": {"autoClose": "1800s"},
        "conditions": [condition]})
    print("created policy", name)

def uptime_condition(check, label):
    check_id = check["name"].split("/")[-1]
    return {"displayName": label, "conditionThreshold": {
        "filter": f'metric.type="monitoring.googleapis.com/uptime_check/check_passed" AND resource.type="uptime_url" AND metric.label.check_id="{check_id}"',
        "aggregations": [{"alignmentPeriod": "1200s", "perSeriesAligner": "ALIGN_NEXT_OLDER",
                          "crossSeriesReducer": "REDUCE_COUNT_FALSE", "groupByFields": ["resource.label.*"]}],
        "comparison": "COMPARISON_GT", "thresholdValue": 1, "duration": "60s",
        "trigger": {"count": 1}}}

def log_count_condition(metric, label, threshold, window, duration="0s"):
    return {"displayName": label, "conditionThreshold": {
        "filter": f'metric.type="logging.googleapis.com/user/{metric}" AND resource.type="cloud_run_revision"',
        "aggregations": [{"alignmentPeriod": window, "perSeriesAligner": "ALIGN_DELTA",
                          "crossSeriesReducer": "REDUCE_SUM"}],
        "comparison": "COMPARISON_GT", "thresholdValue": threshold, "duration": duration,
        "trigger": {"count": 1}}}

RUNBOOK = ("Engine: https://console.cloud.google.com/run/detail/us-central1/sector-engine\n\n"
           "Logs: `gcloud run services logs read sector-engine --region us-central1 --project sector-9393c --limit 100`\n\n"
           "Rollback: `./deploy.sh --rollback <previous-revision>` from the Sector_Engine repo.")

policy("Sector engine DOWN (/health failing)",
       "The engine's /health uptime check is failing from 2+ regions.\n\n" + RUNBOOK,
       uptime_condition(up_health, "/health failing from 2+ regions"))
policy("Sector engine not producing conditions",
       "A real /conditions render for Guntersville is failing or missing weather — the app would show no conditions.\n\n" + RUNBOOK,
       uptime_condition(up_deep, "/conditions render failing from 2+ regions"))
policy("Sector engine 5xx errors",
       "More than 10 server errors (5xx) in 5 minutes — users are seeing failures.\n\n" + RUNBOOK,
       {"displayName": "5xx > 10 in 5 min", "conditionThreshold": {
           "filter": f'metric.type="run.googleapis.com/request_count" AND resource.type="cloud_run_revision" AND resource.label.service_name="{SERVICE}" AND metric.label.response_code_class="5xx"',
           "aggregations": [{"alignmentPeriod": "300s", "perSeriesAligner": "ALIGN_DELTA",
                             "crossSeriesReducer": "REDUCE_SUM"}],
           "comparison": "COMPARISON_GT", "thresholdValue": 10, "duration": "0s", "trigger": {"count": 1}}})
policy("Sector engine slow (p95 > 20s)",
       "95th-percentile request latency above 20 seconds for 10 minutes.\n\n" + RUNBOOK,
       {"displayName": "p95 latency > 20s", "conditionThreshold": {
           "filter": f'metric.type="run.googleapis.com/request_latencies" AND resource.type="cloud_run_revision" AND resource.label.service_name="{SERVICE}"',
           "aggregations": [{"alignmentPeriod": "300s", "perSeriesAligner": "ALIGN_PERCENTILE_95",
                             "crossSeriesReducer": "REDUCE_MAX"}],
           "comparison": "COMPARISON_GT", "thresholdValue": 20000, "duration": "600s", "trigger": {"count": 1}}})
policy("Sector engine crashed",
       "An engine container crashed (signal) or was terminated.\n\n" + RUNBOOK,
       log_count_condition("engine_container_crash", "container crash", 0, "300s"))
policy("Sector engine can't score (weather outage)",
       "More than 20 renders refused for missing weather in 10 minutes — Open-Meteo is failing or rate-limiting.\n\n" + RUNBOOK,
       log_count_condition("engine_render_unavailable", "no-weather renders > 20 / 10 min", 20, "600s"))
policy("Sector engine Remote Config rejected",
       "A conditions_config edit in the Firebase console failed validation and was NOT applied. Fix the value in the console.\n\n" + RUNBOOK,
       log_count_condition("engine_remote_config_rejected", "remote config rejected", 0, "300s"))
print("done")
