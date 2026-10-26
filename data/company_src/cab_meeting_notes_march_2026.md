title: Change Advisory Board Notes - March 2026
format: docx
author: Daniel Okafor
date: 2026-03-11

# Change Advisory Board - meeting notes, March 2026

Meetings of 5 March and 11 March 2026. Chair: Marta Silva (Head of Engineering). Notes: Daniel Okafor.

## 5 March 2026

CHG-0412, payments-api v4.2: shorter idempotency-key TTL, from 24 hours to 10 minutes. Reason: Redis memory pressure in February. The Payments team said that clients rarely reuse a key after a few minutes. Rated low risk. Approved for 9 March.

## 11 March 2026

CHG-0415, api-gateway: per-merchant rate limit from 50 to 80 requests per second. Approved for 12 March.

CHG-0419, fraud-scorer model v7. The Fraud team showed better fraud detection in offline tests and a load test at night-time traffic with a p99 latency of 310 ms. Rated medium risk because it changes blocking decisions. Approved for 17 March, deployment after 18:00 UTC.

## Follow-up added on 25 March 2026

After INC-2026-031, CAB requires a load test at peak traffic for every fraud-scorer model and a check of client retry behaviour for every idempotency change.
