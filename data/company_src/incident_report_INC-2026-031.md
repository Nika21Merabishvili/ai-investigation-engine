title: Incident Report INC-2026-031
format: pdf
author: Lena Fischer
date: 2026-03-18

# Incident Report: INC-2026-031 - duplicate card charges

Severity: SEV-1
Date: 18 March 2026
Incident commander: Lena Fischer (SRE)
Status: Resolved

## Summary

Between 09:40 and 11:33 UTC on 18 March 2026, NovaPay captured some card payments twice. Merchants received a timeout (HTTP 504) for payments that had in fact succeeded. The NovaPay server SDK retried those payments later, and they were captured a second time.

## Impact

- 1,284 card payments were charged twice.
- 212 merchants were affected.
- Duplicated amount: EUR 186,420.
- No data was lost and no card details were exposed.

## Timeline (UTC)

- 09:25 fraud-scorer latency starts rising with morning traffic.
- 09:40 first duplicate charge is captured.
- 10:22 ledger-service reconciliation alert: duplicate-amount anomaly.
- 10:31 incident declared SEV-1.
- 11:05 fraud-scorer rolled back from model v7 to v6.
- 11:33 last duplicate charge.
- 12:40 payments-api hotfix v4.2.1 deployed.
- 13:05 incident resolved.

## Next steps

Finance and Support will refund every duplicate charge. A full postmortem will follow within five working days.
