"""
Gunicorn Configuration for Production

Run with: gunicorn main:app -c gunicorn.conf.py

This configuration is optimized for small servers (t2.micro/t3.micro)
with browser automation workloads.

MEMORY REQUIREMENTS:
- Base App (1 worker): ~150MB
- Browser Pool (shared): ~300MB
- Per Browser Context: ~50MB
- Total for t2.micro (1GB): ~500-600MB with 1-2 workers

RECOMMENDED SETTINGS BY INSTANCE:
- t2.micro (1GB RAM):  GUNICORN_WORKERS=1, BROWSER_POOL_MAX_CONTEXTS=3
- t2.small (2GB RAM):  GUNICORN_WORKERS=2, BROWSER_POOL_MAX_CONTEXTS=5
- t2.medium (4GB RAM): GUNICORN_WORKERS=3, BROWSER_POOL_MAX_CONTEXTS=8
"""

import multiprocessing
import os

# =============================================================================
# Server Socket
# =============================================================================

bind = "0.0.0.0:8000"
backlog = 2048

# =============================================================================
# Worker Processes
# =============================================================================

# LOW_MEMORY_MODE: Set to "true" for t2.micro/t3.micro (1GB RAM)
# This drastically reduces memory usage for browser automation workloads
LOW_MEMORY_MODE = os.getenv("LOW_MEMORY_MODE", "true").lower() == "true"

if LOW_MEMORY_MODE:
    # For 1GB RAM servers: 1 worker only
    # Each worker can handle many async requests via browser pool
    workers = int(os.getenv("GUNICORN_WORKERS", "1"))
else:
    # For larger servers: 2-4 workers based on CPU
    workers = int(os.getenv("GUNICORN_WORKERS", min(2 * multiprocessing.cpu_count() + 1, 4)))

# Use Uvicorn worker for async support
worker_class = "uvicorn.workers.UvicornWorker"

# Threads per worker (reduced for low memory)
threads = 1 if LOW_MEMORY_MODE else 2

# Worker timeout (increase for long-running form operations)
timeout = 120
graceful_timeout = 30
keepalive = 5

# Max requests per worker before restart (prevents memory leaks)
# Reduced for low memory mode to reclaim memory more frequently
max_requests = 500 if LOW_MEMORY_MODE else 1000
max_requests_jitter = 50 if LOW_MEMORY_MODE else 100

# =============================================================================
# Memory Optimization
# =============================================================================

# Preload app to share memory across workers (saves ~50MB per worker)
preload_app = True

# =============================================================================
# Logging
# =============================================================================

accesslog = "-"  # stdout
errorlog = "-"   # stderr
loglevel = os.getenv("LOG_LEVEL", "info")

# Access log format
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# =============================================================================
# Process Naming
# =============================================================================

proc_name = "formflow-api"

# =============================================================================
# Server Mechanics
# =============================================================================

daemon = False
pidfile = None
user = None
group = None
tmp_upload_dir = None

# =============================================================================
# Hooks
# =============================================================================

def on_starting(server):
    """Called just before the master process is initialized."""
    pass

def on_exit(server):
    """Called just before the master process exits."""
    pass

def worker_exit(server, worker):
    """Called when a worker exits."""
    pass
