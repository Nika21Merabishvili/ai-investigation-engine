title: Postmortem INC-2026-031: Duplicate Card Charges
format: docx
author: Lena Fischer
date: 2026-03-24

# Postmortem: INC-2026-031 duplicate card charges

Blameless review, written 24 March 2026. Authors: Lena Fischer (SRE), Tomas Novak (Payments), Priya Raman (Fraud).

## What happened

On 18 March 2026, 1,284 card payments across 212 merchants were charged twice, for a total of EUR 186,420. The first duplicate was captured at 09:40 UTC and the last at 11:33 UTC.

## Root cause

Two changes from March combined. CHG-0412 (9 March) lowered the idempotency-key TTL in payments-api from 24 hours to 10 minutes. CHG-0419 (17 March) deployed fraud-scorer model v7, which was much slower under load: at the morning peak its p99 latency went from about 250 ms to 6 seconds.

payments-api waits up to 8 seconds for fraud-scorer, but api-gateway gives up after 5 seconds. Merchants therefore got HTTP 504 while payments-api went on to capture the payment. The NovaPay server SDK retries a 504 after 15 minutes with the same idempotency key. Because the key had already expired after 10 minutes, payments-api treated the retry as a new payment and charged the card again.

## Contributing factors

- CHG-0412 was rated low risk without checking the SDK retry schedule.
- fraud-scorer v7 was load-tested at night-time traffic only.
- The api-gateway timeout (5 seconds) is shorter than the payments-api timeout for fraud-scorer (8 seconds).

## What went well

The ledger-service reconciliation alert caught the anomaly. The fraud-scorer rollback took 12 minutes and followed the runbook.

## Action items

Tracked in the INC-2026-031 action item tracker.
