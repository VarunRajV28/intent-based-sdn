#!/usr/bin/env bash
# network/run_controllers.sh
# Owner: Anuj
# Purpose: Start / stop the three Ryu controller processes.
#
# Usage:
#   bash network/run_controllers.sh start   # start c1, c2, c3
#   bash network/run_controllers.sh stop    # kill all three
#   bash network/run_controllers.sh kill c1 # kill only c1 (for failover demo)
#
# Each controller loads two apps:
#   controllers/base_app.py   (Anuj)  - table-miss + learned forwarding + roles
#   controllers/rule_api.py   (Narain) - REST endpoints for intent rules
#
# Environment variables passed to each controller:
#   CONTROLLER_ID  - c1, c2, or c3
#   REST_PORT      - 8081, 8082, or 8083
#   OF_PORT        - 6653, 6654, or 6655
#
# TODO (Anuj):
#   Fill in the ryu-manager commands, log file paths, and PID management.
#   Example for c1:
#     CONTROLLER_ID=c1 REST_PORT=8081 \
#       ryu-manager --ofp-tcp-listen-port 6653 \
#         controllers/base_app.py controllers/rule_api.py \
#         > logs/c1.log 2>&1 &
#     echo $! > logs/c1.pid

set -euo pipefail
mkdir -p logs

case "${1:-start}" in
  start)
    echo "TODO: start c1, c2, c3"
    ;;
  stop)
    echo "TODO: kill all controllers"
    ;;
  kill)
    echo "TODO: kill controller ${2:-c1}"
    ;;
  *)
    echo "Usage: $0 {start|stop|kill <cN>}"
    exit 1
    ;;
esac
