# orchestrator/mock_controller.py
# Owner: Varun
# Purpose: Tiny in-memory Flask imitation of a Ryu controller's REST API (section 4.3),
#          so the orchestrator and monitor can be developed on Windows with no Ryu/Mininet.
#
# Run ONE controller per terminal (the port defaults to the controller's REST port):
#   python orchestrator/mock_controller.py --id c1 --port 8081
#   python orchestrator/mock_controller.py --id c2 --port 8082
#   python orchestrator/mock_controller.py --id c3 --port 8083
# ...or all three in one process:
#   python orchestrator/mock_controller.py --all
# (CONTROLLER_ID and REST_PORT environment variables also work.)
#
# Endpoints (section 4.3):
#   GET    /status               -> {controller_id, mastered_dpids, rule_count}
#   GET    /flows?dpid=N         -> list of flow entries on switch N
#   POST   /rules                body: sub-policy + intent_id -> {"ok": true|false}
#   DELETE /rules/<intent_id>    -> remove every rule with that cookie
#   POST   /takeover             body: {dpids: [...], rules: [...]} -> become master, install
#
# Like the real controller, POST /rules only works for a switch this controller masters
# (HTTP 409 + {"ok": false} otherwise). A rule may carry "intent_id" (the cookie).
# Everything lives in memory: restart the process and all state is gone.

from __future__ import annotations

import argparse
import json
import os
import threading
from pathlib import Path

from flask import Flask, jsonify, request

TOPOLOGY_PATH = Path(__file__).resolve().parent.parent / "shared" / "topology.json"


def _load_topology():
    try:
        with open(TOPOLOGY_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def create_app(controller_id, mastered_dpids=None, topology=None):
    """Build a Flask app that behaves like controller `controller_id`."""
    topology = topology or _load_topology()
    if mastered_dpids is None:
        mastered_dpids = [int(s["dpid"]) for s in (topology or {}).get("switches", [])
                          if s["default_owner"] == controller_id]

    app = Flask("mock_" + controller_id)
    lock = threading.Lock()
    state = {"dpids": set(int(d) for d in mastered_dpids), "rules": []}   # rules: flow entries
    app.state = state   # handy for tests

    def make_rule(body, fallback_intent_id=None):
        """Validate a sub-policy dict and turn it into a stored flow entry."""
        if not isinstance(body, dict) or "dpid" not in body or "match" not in body:
            raise ValueError("body needs at least 'dpid' and 'match'")
        match = body["match"]
        if not isinstance(match, dict) or "eth_type" not in match or not (
                "ipv4_src" in match or "ipv4_dst" in match):
            raise ValueError("match needs eth_type and ipv4_src and/or ipv4_dst")
        intent_id = body.get("intent_id", fallback_intent_id)
        if intent_id is None:
            raise ValueError("missing intent_id")
        return {
            "dpid": int(body["dpid"]),
            "priority": int(body.get("priority", 100)),
            "cookie": int(intent_id),
            "match": dict(match),
            "instructions": [],          # empty instruction list == drop
        }

    def install(rule):
        """Add a flow entry unless an identical one (same cookie+dpid+match) exists."""
        for r in state["rules"]:
            if (r["dpid"], r["cookie"], r["match"]) == (rule["dpid"], rule["cookie"], rule["match"]):
                return
        state["rules"].append(rule)

    @app.get("/status")
    def status():
        with lock:
            return jsonify({
                "controller_id": controller_id,
                "mastered_dpids": sorted(state["dpids"]),
                "rule_count": len(state["rules"]),
            })

    @app.get("/flows")
    def flows():
        try:
            dpid = int(request.args["dpid"])
        except (KeyError, ValueError):
            return jsonify({"ok": False, "error": "query parameter dpid=N is required"}), 400
        with lock:
            entries = []
            if dpid in state["dpids"]:
                entries.append({"dpid": dpid, "priority": 0, "cookie": 0, "match": {},
                                "instructions": ["OUTPUT:CONTROLLER"]})   # fake table-miss
                entries += [dict(r) for r in state["rules"] if r["dpid"] == dpid]
            return jsonify(entries)

    @app.post("/rules")
    def post_rule():
        body = request.get_json(silent=True)
        try:
            rule = make_rule(body)
        except (ValueError, TypeError) as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        with lock:
            if rule["dpid"] not in state["dpids"]:
                return jsonify({"ok": False,
                                "error": "%s is not master of dpid %d" % (controller_id, rule["dpid"])}), 409
            install(rule)
        return jsonify({"ok": True})

    @app.delete("/rules/<int:intent_id>")
    def delete_rule(intent_id):
        with lock:
            before = len(state["rules"])
            state["rules"] = [r for r in state["rules"] if r["cookie"] != intent_id]
            removed = before - len(state["rules"])
        return jsonify({"ok": True, "removed": removed})

    @app.post("/takeover")
    def takeover():
        body = request.get_json(silent=True) or {}
        dpids, rules = body.get("dpids"), body.get("rules", [])
        if not isinstance(dpids, list) or not dpids:
            return jsonify({"ok": False, "error": "'dpids' (non-empty list) is required"}), 400
        try:
            new_rules = [make_rule(r) for r in rules]
        except (ValueError, TypeError) as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        with lock:
            state["dpids"].update(int(d) for d in dpids)           # RoleRequest MASTER
            installed = 0
            for rule in new_rules:
                if rule["dpid"] in state["dpids"]:
                    install(rule)
                    installed += 1
        return jsonify({"ok": True, "mastered_dpids": sorted(state["dpids"]), "installed": installed})

    return app


def _rest_port_for(controller_id, topology):
    for c in (topology or {}).get("controllers", []):
        if c["id"] == controller_id:
            return int(c["rest_port"])
    return {"c1": 8081, "c2": 8082, "c3": 8083}.get(controller_id, 8081)


def run_all(host):
    """Start c1, c2, c3 in one process (one thread each). Ctrl+C stops all three."""
    from werkzeug.serving import make_server
    topology = _load_topology()
    servers = []
    for cid in ("c1", "c2", "c3"):
        port = _rest_port_for(cid, topology)
        server = make_server(host, port, create_app(cid, topology=topology), threaded=True)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        print("mock controller %s listening on http://%s:%d" % (cid, host, port))
    print("Press Ctrl+C to stop all.")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        for s in servers:
            s.shutdown()


def main():
    ap = argparse.ArgumentParser(description="In-memory mock of a Ryu controller REST API")
    ap.add_argument("--id", default=os.environ.get("CONTROLLER_ID", "c1"), help="c1, c2 or c3")
    ap.add_argument("--port", type=int, default=os.environ.get("REST_PORT"),
                    help="REST port (default: 8081/8082/8083 by id)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--all", action="store_true", help="run c1, c2 and c3 in this one process")
    args = ap.parse_args()

    if args.all:
        run_all(args.host)
        return
    topology = _load_topology()
    port = int(args.port) if args.port else _rest_port_for(args.id, topology)
    app = create_app(args.id, topology=topology)
    print("mock controller %s listening on http://%s:%d (masters dpids %s)"
          % (args.id, args.host, port, sorted(app.state["dpids"])))
    app.run(host=args.host, port=port, threaded=True, debug=False)


if __name__ == "__main__":
    main()
