"""Gunicorn configuration tuned for Render deployment."""

import multiprocessing
import os

port = os.environ.get("PORT", "10000")
bind = f"0.0.0.0:{port}"

# Keep worker count conservative for free/small plans to avoid OOM.
workers = int(os.environ.get("GUNICORN_WORKERS", max(2, multiprocessing.cpu_count() // 2)))
threads = int(os.environ.get("GUNICORN_THREADS", 4))
timeout = int(os.environ.get("GUNICORN_TIMEOUT", 120))
