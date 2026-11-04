<!-- artifact file of the paper "Predictable-Cost Autoscaling of a Three-Layer 5G User Plane with Library-Calibrated Risk" (docs/paper), written 2026-10-21 (R64, spec §4.109) when the Simulation subsections "Decision equivalence" and "The −2 % source" were merged and halved for the page limit; full text and numbers verbatim from the r63 version, source comments kept. -->

# Decision equivalence and the −2 % source (full text)

## Decision equivalence

The deployed daemon and nest2 take identical decisions on traces t1 and t2 at both operating points. A Go test drives the real daemon decision path (`V6Shadow.Tick → reconcileInflight → decideQuantile → Controller.V6Decisions`) on the nest2 time axis through a clock hook, and compares the per-tick action multiset with nest2. <!-- §4.19 item 6 --> On t1 and t2 at both operating points the multisets differ in 0 ticks, with identical allocation (1207/1207, 1411/1411, 1103/1103, 1308/1308 core-min). <!-- §4.19 item 6 --> A scenario with a 0.7 % pps bias shows 0 to 2 differing ticks, explained by a one-tick release shift. <!-- §4.19 item 6 --> Running the test against the previous daemon version reproduces two known divergences, which shows the test is sensitive. <!-- §4.19 item 6 -->

## The −2 % source

The −2 % gap on t1 came from the billing convention for VM existence, not from decisions. Before the convention change, t1 runs were systematically about 2 % cheaper than predicted while t2 runs were within ±1 %, and per-minute comparison located the gap on the release side. <!-- §4.25 --> Host sampling showed QEMU processes appear 22 to 38 s after the create order and vanish 3 to 8 s after the delete order, while the simulator billed until the end of the teardown lead (60 s VY, 90 s WK). <!-- §4.25 --> With two VY and three WK create/delete cycles on t1 this is about 20 core-min, or 2 %; t2 has fewer cycles, under 1 %. <!-- §4.25 --> The billing convention was aligned to measured VM existence; the daemon was not changed. <!-- §4.26 item 3 -->

