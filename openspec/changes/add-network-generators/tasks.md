## 1. Branch and campus template (B, H1.5 to H4)

- [x] 1.1 Create the branch `feat/add-network-generators` from an up-to-date `main`
- [x] 1.2 B draws the campus template by hand (core mesh, distribution, building switches, key-service nodes, primary uplink) and its traffic at load factor about 0.5; all four members agree to the new fixture, then it is saved under `fixtures/` with a test that it validates
- [x] 1.3 Add the generator registry and `TopologySpec` resolution for `{template: "campus"}`, with tests: template loads identically twice, unknown name raises

## 2. Traffic generator (B, H1.5 to H4)

- [x] 2.1 Add explicit-list `TrafficSpec` resolution, with a test that the two diamond flows pass through unchanged
- [ ] 2.2 Add the seeded traffic generator (explicit `random.Random(seed)`, largest-remainder class counts, integer rates of at least 1, distinct endpoints), with tests: same seed gives identical flows, 200 flows with unique ids, the class-mix counts
- [ ] 2.3 Give P0 flows a key-service endpoint and a `service` label, with a test on the campus template

## 3. Post-failure path check (B, at H4)

- [x] 3.1 Add the path check (fail the primary uplink on a copy, node-disjoint paths per building, combined capacity against P0 plus P1 demand), with tests: a hand-made network with one remaining path fails and names the building
- [x] 3.2 Add the test that the campus template passes the check; if it fails (assumption A1), all four members agree to add redundancy to the template fixture, then the fixture is changed

## 4. Demo-network tuning (B, H8 to H10)

- [ ] 4.1 Run S0, S0-QoS and S2 on the template with the uplink failed and record `DR`, `DR_P1`, `DR_P0` in the pull request description
- [ ] 4.2 If S2 only ties S0-QoS, all four members agree to a second, longer path with spare capacity; then update the template fixture and its traffic, keeping the path-check test passing

## 5. Campus generator and load scaling (B, H8 to H12)

- [ ] 5.1 Add the campus generator (`buildings`, `redundancy`, `seed`; counter-based ids; designated uplink), with tests: same seed gives identical JSON, different seeds differ, the network is connected
- [ ] 5.2 Wire the path check into the generator with retry up to 20 seeds and effective-seed reporting, with tests: retry reports the passing seed, exhaustion raises with the reason
- [ ] 5.3 Add load-factor scaling of a flow list, with tests: scaling by 1.5 keeps ids, endpoints and classes with integer rates, scaling by 1.0 is the identity
- [ ] 5.4 Set the default parameters to give about 50 nodes and 200 flows, with a test on the node and flow counts

## 6. Integrate

- [ ] 6.1 Run the full test suite with `pytest`, and `check_invariants` on a snapshot of the template and of one generated network under each policy
- [ ] 6.2 Rebase onto `main`
- [ ] 6.3 Run `sh .github/scripts/check-history.sh`
- [ ] 6.4 Open the pull request from `.github/pull_request_template.md`
