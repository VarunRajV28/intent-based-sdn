# network/topo.py
# Owner: Anuj
# Purpose: Build the 6-switch Mininet topology defined in section 4.1.
#
# Run with:   sudo python3 network/topo.py
# (Runs OUTSIDE the venv; uses the system Mininet package from apt.)
#
# Topology (chain):
#   h1 -- s1 -- s2 -- s3 -- s4 -- s5 -- s6 -- h6
#          |         |              |
#         h2        h3 h4          h5
#
# Exact layout (section 4.1):
#   s1 (dpid 1)  -- h1  10.0.1.1/8  MAC 00:00:00:00:00:01  group: guest
#   s2 (dpid 2)  -- h2  10.0.1.2/8  MAC 00:00:00:00:00:02  group: guest
#   s3 (dpid 3)  -- h3  10.0.2.1/8  MAC 00:00:00:00:00:03  group: staff
#   s4 (dpid 4)  -- h4  10.0.2.2/8  MAC 00:00:00:00:00:04  group: staff
#   s5 (dpid 5)  -- h5  10.0.3.1/8  MAC 00:00:00:00:00:05  group: server
#   s6 (dpid 6)  -- h6  10.0.3.2/8  MAC 00:00:00:00:00:06  group: server
#
# Every switch connects to ALL THREE controllers (needed for failover):
#   c1: OpenFlow port 6653
#   c2: OpenFlow port 6654
#   c3: OpenFlow port 6655
#
# TODO (Anuj):
#   1. Import Mininet classes (Mininet, OVSSwitch, RemoteController, Host, Link, CLI).
#   2. Create 3 RemoteController objects on 127.0.0.1 at ports 6653–6655.
#   3. Create 6 OVSSwitch objects with OpenFlow 1.3 protocol and explicit dpids.
#   4. Create 6 Host objects with fixed IPs (/8 netmask) and fixed MACs.
#   5. Add the 5 switch-switch links (s1-s2, s2-s3, s3-s4, s4-s5, s5-s6).
#   6. Add 6 host-switch links.
#   7. Connect each switch to ALL 3 controllers.
#   8. Start the network, drop into CLI, then stop cleanly.
#   9. Verify: 'mininet> net' should list 3 controllers per switch.
