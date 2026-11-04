| λ set | arm | ε | mean risk ± SE | frac traces ≥1 viol | mean alloc vmexist ± SE | risk/ε | T1 verdict |
|---|---|---|---|---|---|---|---|
| S4b new (1.88/2.00) | S4b | 0.02 | 0.213% ± 0.034 | 8.8% | 1131.6 ± 9.1 | 0.11 | conservative, transfers |
| S4a new (2.75/3.12) | S4a | 0.005 | 0.048% ± 0.017 | 1.6% | 1226.2 ± 8.1 | 0.10 | conservative, transfers |
| S4b deployed (1.83/2.00) | S4b | 0.02 | 0.213% ± 0.034 | 8.8% | 1130.5 ± 9.0 | 0.11 | conservative, transfers |
| S4a deployed (2.83/3.08) | S4a | 0.005 | 0.048% ± 0.016 | 1.8% | 1224.5 ± 8.3 | 0.10 | conservative, transfers |
| S4b new unrounded (1.875/2.00) | S4b | 0.02 | 0.213% ± 0.034 | 8.8% | 1131.6 ± 9.1 | 0.11 | conservative, transfers |
| S4a new unrounded (2.75/3.125) | S4a | 0.005 | 0.048% ± 0.017 | 1.6% | 1226.2 ± 8.1 | 0.10 | conservative, transfers |

reproduce madrid/REPORT.md T1 S4a (0.048%, 1224.5): MATCH (fresh 0.0480%, 1224.46)

reproduce madrid/REPORT.md T1 S4b (0.213%, 1130.5): MATCH (fresh 0.2128%, 1130.47)
