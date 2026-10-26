title: Production Change Log - March 2026
format: md

# Production change log - March 2026

Every production change is approved by the Change Advisory Board (CAB) or raised as an emergency change.

## CHG-0405 - 3 March 2026

- Service: webhook-dispatcher
- Change: rotated the TLS client certificate used for merchant webhooks.
- Risk: low. Owner: Platform team.

## CHG-0409 - 5 March 2026

- Service: settlement-batch
- Change: moved the nightly settlement run from 01:00 to 02:00 UTC.
- Risk: low. Owner: Finance Engineering.

## CHG-0412 - 9 March 2026

- Service: payments-api v4.2
- Change: idempotency-key TTL in Redis reduced from 24 hours to 10 minutes to reduce Redis memory use.
- Risk: low. Owner: Payments team (Tomas Novak).

## CHG-0415 - 12 March 2026

- Service: api-gateway
- Change: per-merchant rate limit raised from 50 to 80 requests per second.
- Risk: low. Owner: Platform team.

## CHG-0419 - 17 March 2026, 18:10 UTC

- Service: fraud-scorer
- Change: deployed risk model v7, replacing v6.
- Risk: medium. Owner: Fraud team (Priya Raman).

## CHG-0422 - 18 March 2026, 11:05 UTC (emergency)

- Service: fraud-scorer
- Change: rolled back the risk model from v7 to v6 during INC-2026-031.
- Owner: SRE on call (Daniel Okafor).

## CHG-0423 - 18 March 2026, 12:40 UTC (emergency)

- Service: payments-api v4.2.1
- Change: idempotency-key TTL raised from 10 minutes to 48 hours, longer than every SDK retry.
- Owner: Payments team (Tomas Novak).
