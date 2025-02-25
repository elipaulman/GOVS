# gunicorn_config.py

bind = "0.0.0.0:10000"
workers = 2  # Number of worker processes
threads = 4  # Number of threads per worker
timeout = 120  # Timeout in seconds