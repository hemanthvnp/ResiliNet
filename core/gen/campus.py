"""Campus network: the hand-drawn template's metadata (and, later, the seeded generator).

The template itself is the fixture fixtures/topologies/campus.json, tuned by hand
(PLAN.md sections 9 and 12). The frozen Topology has no field for the primary
uplink, so its id lives here, next to the loader that knows which fixture it belongs to.
Node roles are carried in Node.type: core, distribution, building, hostel, service.
"""

CAMPUS_PRIMARY_UPLINK = "L6"  # D1-C1; failing it is scenario 2 and the section 9 path check
