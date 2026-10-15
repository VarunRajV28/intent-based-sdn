#!/usr/bin/env bash
# demo/demo.sh
# Owner: Narain
# Purpose: Step-by-step demo script for section 8 of the execution plan.
#
# IMPORTANT: Run this only after all three controllers and Mininet are up.
#
# Steps:
#   1. Hand-written rules showcase  (ovs-ofctl dump/add/del)
#   2. Normal intent                ("block guest from server")
#   3. Host-level intents           (disable h3, block h2 and h5, enable h3)
#   4. Failover                     (kill c1, show monitor recovery)
#   5. Unsafe intent                ("block staff from server")
#   6. Surprise intent              ("isolate h4")
#
# TODO (Narain): Fill in the exact commands following demo_script.md.
echo "Demo step 1: hand-written rules showcase"
echo "TODO: add ovs-ofctl commands"
