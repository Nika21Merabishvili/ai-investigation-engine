title: NovaPay Platform Architecture Overview
format: pdf
author: Marta Silva
date: 2026-01-15

# NovaPay platform architecture overview

Owner: Marta Silva, Head of Engineering. Version: January 2026.

## Who we are

NovaPay processes card payments for about 3,000 online merchants in Europe. Merchants integrate through the NovaPay server SDK or call the REST API directly.

## Services

- api-gateway: public entry point, authentication and rate limits.
- payments-api: creates, authorizes and captures payments; stores idempotency keys in Redis.
- fraud-scorer: returns a risk score for each payment and is called synchronously.
- ledger-service: double-entry ledger and reconciliation.
- webhook-dispatcher: sends payment events to merchants.
- settlement-batch: nightly payouts to merchants.

## Request path for a card payment

The merchant calls POST /v1/payments on api-gateway. The gateway forwards the request to payments-api, which checks the idempotency key, asks fraud-scorer for a score, authorizes and captures the payment with the card acquirer, and records it in ledger-service. webhook-dispatcher then notifies the merchant.

## Data stores

- PostgreSQL for payments and the ledger.
- Redis for idempotency keys and rate-limit counters.
- Object storage for acquirer settlement files.

## Hosting

All services run on Kubernetes in two EU regions. Payment traffic is active in one region at a time.
