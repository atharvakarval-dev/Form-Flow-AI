"""
Gunicorn Configuration for Production

Run with: gunicorn main:app -c gunicorn.conf.py

This configuration is optimized for small servers (t3.micro/t3.small)
handling 1000+ concurrent users.
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

# For small servers: 2-4 workers
# Formula: min(2 * CPU + 1, 4) for memory-constrained servers
workers = int(os.getenv("GUNICORN_WORKERS", min(2 * multiprocessing.cpu_count() + 1, 4)))

# Use Uvicorn worker for async support
worker_class = "uvicorn.workers.UvicornWorker"

# Threads per worker (for I/O bound work)
threads = 2

# Worker timeout (increase for long-running form operations)
timeout = 120
graceful_timeout = 30
keepalive = 5

# Max requests per worker before restart (prevents memory leaks)
max_requests = 1000
max_requests_jitter = 100

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
