# Intent-Based Multi-Controller SDN

**Team:** Varun · Anuj · Narain · Karthik

## Quick-start for each person

### Varun & Karthik (no Mininet required)

```bash
# From the repo root
python3.9 -m venv .venv
source .venv/bin/activate                   # Windows: .venv\Scripts\activate
python -m pip install pip==23.3.2 setuptools==65.5.1 wheel==0.42.0
pip install -r requirements-orchestrator.txt
pytest orchestrator/tests/                  # should collect & pass (stubs)
```

### Anuj & Narain (Ubuntu with Mininet + Ryu)

```bash
# Check existing Ryu (do NOT reinstall or upgrade)
ryu-manager --version

# Install Mininet and OVS if missing
sudo apt install mininet openvswitch-switch

# Quick smoke-test
sudo mn --test pingall

# Start controllers (fill in run_controllers.sh first)
bash network/run_controllers.sh start

# Start Mininet topology
sudo python3 network/topo.py
```

## Repo layout

```
intent-based-sdn/
├── requirements-orchestrator.txt   # Varun & Karthik — exact pinned versions
├── shared/
│   ├── topology.json               # canonical topology (Varun, hour 0)
│   └── store.json                  # runtime intent store (auto-managed)
├── orchestrator/                   # Varun & Karthik — pure Python, no Mininet
│   ├── parser.py                   # Varun: text → policy dict
│   ├── decomposer.py               # Varun: policy → sub-policies per controller
│   ├── store.py                    # Varun: JSON file store with file locking
│   ├── mock_controller.py          # Varun: Flask mock of the real REST API
│   ├── orchestrator.py             # Varun: interactive CLI (main entry point)
│   ├── twin.py                     # Karthik: digital-twin safety checker
│   ├── monitor.py                  # Karthik: heartbeat monitor + failover
│   └── tests/
│       ├── test_parser.py          # Varun
│       ├── test_decomposer.py      # Varun
│       ├── test_twin.py            # Karthik
│       └── test_monitor.py         # Karthik
├── network/                        # Anuj — Mininet scripts
│   ├── topo.py                     # 6-switch chain topology
│   └── run_controllers.sh          # start/stop/kill-one script
├── controllers/                    # Anuj + Narain — Ryu apps
│   ├── base_app.py                 # Anuj: table-miss + learned forwarding + roles
│   └── rule_api.py                 # Narain: REST API for intent rules
├── demo/                           # Narain
│   ├── demo.sh                     # exact demo commands
│   └── demo_script.md              # presenter notes
└── slides/                         # Karthik
    └── README.md
```

## Key contracts (do not change after hour 1)

| Contract | File | Section |
|---|---|---|
| Topology | `shared/topology.json` | 4.1 |
| Intent / sub-policy JSON | `orchestrator/decomposer.py` docstring | 4.2 |
| Controller REST API | `controllers/rule_api.py` docstring | 4.3 |
| Intent store API | `orchestrator/store.py` docstring | 4.4 |
| `twin.check` signature | `orchestrator/twin.py` docstring | 4.7 |

## Integration milestones

| Time | Checkpoint |
|---|---|
| Hour 1 | topology.json agreed & pushed; venvs building |
| Hour 5 | Orchestrator ↔ mock, Anuj's network forwarding, Narain's /rules working |
| Hour 7 | First real intent deployed to real controllers |
| Hour 8.5 | Failover works end-to-end |
| Hour 10 | Demo rehearsed ×3, slides done, backup video recorded |
