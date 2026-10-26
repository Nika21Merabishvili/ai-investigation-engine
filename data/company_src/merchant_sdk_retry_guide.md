title: NovaPay Server SDK - Retry Behaviour
format: pdf
author: Developer Experience team
date: 2025-11-10

# NovaPay server SDK - retry behaviour

Applies to the NovaPay server SDK for Java, Python, Node.js and PHP, version 3.x. Owner: Developer Experience team.

## When the SDK retries

The SDK retries a payment request only when it is safe to do so: on network errors and on HTTP 502, 503 and 504. It never retries on 4xx responses.

## Retry schedule

To avoid retry storms during an outage, the SDK does not retry immediately. It puts the request in a local retry queue and sends it again after 15 minutes. If that attempt also fails, it makes one last attempt 30 minutes later.

## Idempotency

Every retry reuses the original Idempotency-Key header. As long as payments-api still holds the key, a retry returns the original result and the card is not charged again.

## Advice for merchants

Do not add your own retries on top of the SDK. After a timeout, show the customer a "payment pending" message and wait for the payment.captured webhook.
