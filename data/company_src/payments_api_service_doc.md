title: payments-api Service Documentation
format: md

# payments-api service documentation

Owner: Payments team. Last updated: 20 February 2026.

## Purpose

payments-api creates, authorizes and captures card payments for merchants. It is the only service that talks to the card acquirer.

## Request flow

1. api-gateway forwards POST /v1/payments to payments-api.
2. payments-api checks the idempotency key in Redis.
3. It calls fraud-scorer for a risk score and waits up to 8 seconds for the answer.
4. If the score is below the block threshold, it authorizes and captures the payment with the acquirer.
5. It writes the charge to ledger-service and emits a payment event for webhook-dispatcher.

## Idempotency

Every payment request must carry an Idempotency-Key header. payments-api stores each key in Redis together with the response it returned. Idempotency keys are kept for 24 hours, so a retry with the same key within 24 hours returns the original result and never charges the card twice.

## Dependencies

Redis (idempotency keys), fraud-scorer, ledger-service and the card acquirer.

## Alerts

- Capture error rate above 2% for 5 minutes pages the Payments team.
