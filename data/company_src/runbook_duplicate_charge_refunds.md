title: Runbook: Refund Duplicate Card Charges
format: docx
author: Ana Beridze
date: 2026-03-21

# Runbook: refund duplicate card charges

Owner: Finance Operations. Last updated: 21 March 2026.

## When to use

Use this runbook when ledger-service or a merchant reports that a cardholder was charged twice for the same order.

## Steps

1. Export the suspected duplicates from the ledger-service reconciliation report.
2. Confirm each pair: same card, same merchant, same amount and the same idempotency key in the request logs.
3. Refund the second charge of each confirmed pair through the refunds API with reason code DUPLICATE.
4. Hold the next payout of every affected merchant in settlement-batch until its refunds are complete.
5. Ask Merchant Support to email the affected merchants.

## Notes

Refunds reach the cardholder within 3 to 5 business days, depending on the issuing bank. Never refund the first charge: it belongs to the order the merchant actually shipped.
