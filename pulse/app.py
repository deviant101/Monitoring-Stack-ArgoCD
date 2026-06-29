"""pulse: a small Flask web app used to demonstrate GitOps image-based
updates.

Routes:
    GET /         -> a simple HTML GUI showing the build version + a live counter
    GET /api/ping -> JSON endpoint the GUI button calls (drives a metric)
    GET /healthz  -> liveness/readiness probe target
    GET /metrics  -> Prometheus metrics
"""

import os
import socket
import time

from flask import Flask, Response, jsonify, render_template_string, request
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# VERSION is injected at build time by the Dockerfile (from a build-arg).
VERSION = os.getenv("VERSION", "dev")

app = Flask(__name__)

REQUESTS_TOTAL = Counter(
    "app_http_requests_total",
    "Total HTTP requests handled, partitioned by path and status code.",
    ["path", "status"],
)
REQUEST_DURATION = Histogram(
    "app_http_request_duration_seconds",
    "HTTP request latency in seconds, partitioned by path.",
    ["path"],
)
PINGS_TOTAL = Counter(
    "app_pings_total",
    "Number of times the GUI Ping button was pressed.",
)
BUILD_INFO = Gauge(
    "app_build_info",
    "Build metadata exposed as a constant 1, labelled by version.",
    ["version"],
)
BUILD_INFO.labels(version=VERSION).set(1)


@app.before_request
def _start_timer():
    request._start_time = time.perf_counter()


@app.after_request
def _record_metrics(response):
    # /metrics scrapes shouldn't recursively instrument themselves.
    if request.path != "/metrics":
        elapsed = time.perf_counter() - getattr(request, "_start_time", time.perf_counter())
        REQUEST_DURATION.labels(path=request.path).observe(elapsed)
        REQUESTS_TOTAL.labels(path=request.path, status=response.status_code).inc()
    return response


INDEX_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>pulse</title>
  <style>
    :root { color-scheme: light dark; }
    body { font-family: system-ui, sans-serif; margin: 0; min-height: 100vh;
           display: grid; place-items: center;
           background: linear-gradient(135deg, #1e3a8a, #6d28d9); color: #fff; }
    .card { background: rgba(255,255,255,0.1); backdrop-filter: blur(8px);
            padding: 2.5rem 3rem; border-radius: 16px; text-align: center;
            box-shadow: 0 10px 40px rgba(0,0,0,0.3); max-width: 420px; }
    h1 { margin: 0 0 .25rem; font-size: 1.8rem; }
    .meta { opacity: .8; font-size: .9rem; margin-bottom: 1.5rem; }
    .meta code { background: rgba(0,0,0,.25); padding: .1rem .4rem; border-radius: 6px; }
    button { font-size: 1rem; padding: .7rem 1.6rem; border: 0; border-radius: 10px;
             cursor: pointer; background: #fff; color: #1e3a8a; font-weight: 600; }
    button:hover { background: #e5e7eb; }
    .count { font-size: 2.5rem; font-weight: 700; margin: 1rem 0; }
    a { color: #c7d2fe; }
  </style>
</head>
<body>
  <div class="card">
    <h1>🚀 pulse</h1>
    <div class="meta">
      version <code>{{ version }}</code> &middot; host <code>{{ host }}</code>
    </div>
    <div class="count" id="count">0</div>
    <button onclick="ping()">Ping</button>
    <p class="meta" style="margin-top:1.5rem">
      <a href="/metrics">/metrics</a> &middot; <a href="/healthz">/healthz</a>
    </p>
  </div>
  <script>
    async function ping() {
      const r = await fetch('/api/ping');
      const d = await r.json();
      document.getElementById('count').textContent = d.pings;
    }
  </script>
</body>
</html>
"""


@app.get("/")
def index():
    return render_template_string(INDEX_HTML, version=VERSION, host=socket.gethostname())


@app.get("/api/ping")
def ping():
    PINGS_TOTAL.inc()
    # _value is the simplest way to echo the current total back to the GUI.
    return jsonify(pings=int(PINGS_TOTAL._value.get()))


@app.get("/healthz")
def healthz():
    return jsonify(status="ok")


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    # Used only for local dev; in the container gunicorn serves the app.
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
