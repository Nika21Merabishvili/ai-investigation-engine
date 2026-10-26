title: Runbook: Redis Memory Pressure
format: txt

RUNBOOK - REDIS MEMORY PRESSURE

Owner: Platform team. Last updated: 27 February 2026.

WHEN TO USE
Use this runbook when the Redis cluster used by payments-api goes above 80% of its memory limit.

WHAT USES THE MEMORY
The largest key family is idempotency keys (prefix idem:), followed by rate-limit counters (prefix rl:). Idempotency keys grow with payment volume and with their TTL.

STEPS
1. Check memory per key prefix on the redis-memory dashboard.
2. If rate-limit counters are growing, look for a stuck api-gateway node.
3. If idempotency keys are growing, ask the Payments team before changing their TTL. A shorter TTL saves memory but also shortens the time in which retries are safe.
4. As a last resort, add a shard. Never flush the cluster.

HISTORY
In February 2026 the cluster reached 86% of its memory limit. The Payments team proposed a shorter idempotency TTL (see CHG-0412).
