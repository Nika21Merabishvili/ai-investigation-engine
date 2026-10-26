title: INC-2026-031 Action Item Tracker
format: md

# INC-2026-031 action item tracker

Owner: Lena Fischer. Last updated: 2 April 2026.

- AI-1: Raise the idempotency-key TTL above the longest SDK retry window. Owner: Tomas Novak. Status: done on 18 March (CHG-0423, 48 hours).
- AI-2: Load-test fraud-scorer models at peak traffic before release. Owner: Priya Raman. Status: in progress, due 30 April.
- AI-3: Make the api-gateway timeout and the payments-api timeout for fraud-scorer consistent. Owner: Platform team. Status: open.
- AI-4: Add an alert on the rate of HTTP 504 for POST /v1/payments. Owner: Daniel Okafor. Status: done on 26 March.
- AI-5: Add a CAB check of client retry behaviour for idempotency changes. Owner: Marta Silva. Status: done on 25 March.
- AI-6: Update the payments-api service documentation after CHG-0412 and CHG-0423. Owner: Payments team. Status: open.
