#!/usr/bin/env sh
set -e

# Entry point for PulsePilot Backend Docker container
# If TASK=worker, start Dramatiq worker; otherwise start Uvicorn web server
if [ "$TASK" = "worker" ]; then
  exec dramatiq tasks.dramatiq_worker --processes ${DRAMATIQ_PROCESSES:-1} --threads ${DRAMATIQ_THREADS:-4}
else
  exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
fi 