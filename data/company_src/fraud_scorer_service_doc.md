title: fraud-scorer Service Documentation
format: pdf
author: Priya Raman
date: 2026-03-25

# fraud-scorer service documentation

Owner: Fraud team (Priya Raman). Last updated: 25 March 2026.

## Purpose

fraud-scorer returns a risk score from 0 to 100 for every card payment. payments-api calls it synchronously before authorization and blocks payments that score 85 or more.

## Models

- v6: gradient-boosted trees with 140 features. In production since November 2025.
- v7: adds device and merchant-history features. Deployed on 17 March 2026 (CHG-0419) and rolled back on 18 March 2026 (CHG-0422) during INC-2026-031.
- v6 is the current production model. v7 will return after a load test at peak traffic.

## Performance targets

- p50 latency below 80 ms.
- p99 latency below 400 ms.
- Measured on 18 March 2026 with v7 at the morning peak: p99 of 6 seconds.

## Operations

Model rollback is described in the fraud-scorer rollback runbook. Since 25 March 2026, CAB requires a load test at peak traffic before any model change.
