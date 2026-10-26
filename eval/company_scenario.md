# NovaPay company corpus: scenario and answer key

Ground truth for the 20 synthetic documents in `data/company/`. This file is the answer key for the Day 4 evaluation: never ingest it.

## Scenario (15 lines)

1. NovaPay processes card payments for about 3,000 online merchants in Europe.
2. Services: api-gateway (public entry, 5 s upstream timeout), payments-api (captures payments, idempotency keys in Redis, waits up to 8 s for fraud-scorer), fraud-scorer (synchronous risk score), ledger-service (double-entry ledger, reconciliation every 15 min), webhook-dispatcher, settlement-batch (nightly payouts at 02:00 UTC).
3. The NovaPay server SDK retries a 504 from a local queue after 15 minutes, then once more 30 minutes later, always with the same idempotency key.
4. Change 1, CHG-0412, 9 March 2026: payments-api v4.2 cut the idempotency-key TTL from 24 hours to 10 minutes to ease Redis memory pressure; CAB rated it low risk.
5. Change 2, CHG-0419, 17 March 2026 at 18:10 UTC: fraud-scorer model v7; at the next morning's peak its p99 latency rose from about 250 ms to 6 s.
6. From 09:25 UTC on 18 March, api-gateway returned 504 after 5 s while payments-api still captured the payment.
7. SDK retries arrived 15 minutes later, after the key had expired, and were captured as new payments: duplicate charges.
8. Incident INC-2026-031 (SEV-1): first duplicate 09:40 UTC, ledger alert 10:22, declared 10:31 by incident commander Lena Fischer.
9. Fix: fraud-scorer rolled back to v6 at 11:05 (CHG-0422); last duplicate 11:33; payments-api v4.2.1 raised the TTL to 48 hours at 12:40 (CHG-0423); resolved 13:05.
10. Impact: 1,284 payments charged twice across 212 merchants, EUR 186,420; refunds finished and held payouts released on 20 March.
11. Contradiction A: the payments-api service doc (last updated February) says keys are kept 24 hours; the change log says 10 minutes from 9 March and 48 hours since 18 March.
12. Contradiction B: the incident report and postmortem count 1,284 duplicate charges; the finance refund memo says 1,317 refunds totalling EUR 191,236.50.
13. Contradiction C: the incident report, postmortem and on-call timeline put the start at 09:40 UTC; the public status page says 10:15 UTC.
14. Missing fact 1: no document says how much Redis memory CHG-0412 saved.
15. Missing fact 2: no document says whether a financial regulator was notified.

## Where each planted item lives

| Item | Side 1 | Side 2 |
| --- | --- | --- |
| A: idempotency-key TTL | `payments_api_service_doc.md` (24 hours) | `change_log_march_2026.md` (10 min, then 48 h), `postmortem_INC-2026-031.docx`, `on_call_timeline_INC-2026-031.txt`, `cab_meeting_notes_march_2026.docx`, `action_items_INC-2026-031.md` (48 h) |
| B: number of duplicate charges | `incident_report_INC-2026-031.pdf`, `postmortem_INC-2026-031.docx` (1,284, EUR 186,420) | `finance_refund_memo.pdf` (1,317, EUR 191,236.50) |
| C: incident start time | `incident_report_INC-2026-031.pdf`, `postmortem_INC-2026-031.docx`, `on_call_timeline_INC-2026-031.txt` (09:40 UTC) | `status_page_updates_march_18.md` (10:15 UTC) |
| Missing 1: Redis memory saved | `runbook_redis_memory_pressure.txt` gives the February level (86%) only | nowhere |
| Missing 2: regulator notified | nowhere | nowhere |

## Distractors

- `webhook_dispatcher_service_doc.md` has its own retry policy (6 attempts over 24 hours). It is not the SDK retry that caused the incident.
- CHG-0405, CHG-0409 and CHG-0415 are unrelated March changes in the same change log.
- `finance_refund_memo.pdf` says acquirer refund fees are still being confirmed, so the fee amount is also unanswerable.
