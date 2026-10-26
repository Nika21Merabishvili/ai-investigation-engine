# webhook-dispatcher service documentation

Owner: Platform team. Last updated: 6 March 2026.

## Purpose

webhook-dispatcher sends payment events (payment.captured, payment.refunded, payout.paid) to the HTTPS endpoint that each merchant registers.

## Retries

If a merchant endpoint does not answer with a 2xx status within 10 seconds, the event is retried up to 6 times over 24 hours, with exponential backoff starting at 1 minute. After the sixth failure the event is marked as failed and shown in the merchant dashboard.

## Security

Each request is signed with an HMAC-SHA256 signature in the NovaPay-Signature header. The TLS client certificate was rotated on 3 March 2026 (CHG-0405).

## Ordering

Events for the same payment are delivered in order. Events for different payments may arrive in any order.
