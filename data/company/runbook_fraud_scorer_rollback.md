# Runbook: roll back the fraud-scorer model

Owner: Fraud team. Last used: 18 March 2026, during INC-2026-031.

## When to use

Use this runbook when a new fraud-scorer model causes high latency, a spike in blocked payments, or errors in payments-api.

## Steps

1. Announce the rollback in the incident channel and open an emergency change.
2. Set FRAUD_MODEL_VERSION to the previous version in the fraud-scorer deployment config.
3. Restart the fraud-scorer pods one at a time: kubectl rollout restart deployment/fraud-scorer.
4. Watch the p99 latency dashboard until it is below 400 ms.
5. Check that the share of blocked payments returns to its normal level, about 0.8%.

## Expected duration

10 to 15 minutes. Pods load the model at start-up, so latency can stay high for a few minutes after the restart.

## If the previous model is also unhealthy

Page the Fraud team lead before changing anything else.
