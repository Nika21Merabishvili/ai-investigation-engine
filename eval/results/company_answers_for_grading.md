# NovaPay answers for hand grading

For each answer write: correct / partly correct / wrong, and for contradiction questions whether the conflict was flagged (yes / no).

## Summary

| Question type | simple: correct / partly / wrong | agent: correct / partly / wrong |
| --- | ---: | ---: |
| simple | 5 / 0 / 0 | 5 / 0 / 0 |
| multi_doc | 2 / 2 / 1 | 2 / 3 / 0 |
| contradiction | 4 / 1 / 0 | 3 / 2 / 0 |
| unanswerable | 3 / 2 / 0 | 3 / 2 / 0 |
| all 20 | 14 / 5 / 1 | 13 / 7 / 0 |
| Contradiction flagged | 4/5 | 3/5 |

**Grading rule.** Correct: the answer gives what the question asks, matching the reference. Partly correct: part of it is right, or the text is right but the status is wrong. Wrong: no answer, or a wrong fact. Citations are judged separately by the script's citation accuracy. Contradiction questions: correct means both sides are stated.

Grades drafted by Claude; reviewed by: ___

## co_simple_01 · simple · expected: answer

**Question:** On what date was fraud-scorer model v7 deployed?

**Reference:** 17 March 2026 (change CHG-0419).

**Gold documents:** Production change log - March 2026

### simple: answered

Fraud-scorer model v7 was deployed on 17 March 2026 [S2][S4][S8].

- Cited: fraud-scorer Service Documentation, Incident Report INC-2026-031, Change Advisory Board Notes - March 2026
- **Grade:** correct (right date; one citation (incident report) has no deploy date, which citation accuracy already counts)

### agent: answered

Fraud-scorer model v7 was deployed on 17 March 2026 [S1][S2].

- Cited: fraud-scorer Service Documentation, Production change log - March 2026
- **Grade:** correct

## co_simple_02 · simple · expected: answer

**Question:** How long does api-gateway wait for a response before it gives up and returns HTTP 504?

**Reference:** 5 seconds.

**Gold documents:** api gateway service doc

### simple: answered

The api-gateway waits 5 seconds for every route before it gives up and returns HTTP 504 Gateway Timeout [S1].

- Cited: api gateway service doc
- **Grade:** correct

### agent: answered

The api-gateway waits for 5 seconds for a response from an internal service before it gives up and returns an HTTP 504 Gateway Timeout [S1].

- Cited: api gateway service doc
- **Grade:** correct

## co_simple_03 · simple · expected: answer

**Question:** At what time was incident INC-2026-031 resolved?

**Reference:** 13:05 UTC on 18 March 2026.

**Gold documents:** Incident Report INC-2026-031

### simple: answered

Incident INC-2026-031 was resolved at 13:05 UTC on 18 March 2026 [S1][S2][S3].

- Cited: on call timeline INC 2026 031, Incident Report INC-2026-031, NovaPay status page - 18 March 2026
- **Grade:** correct (no false conflict)

### agent: answered

Incident INC-2026-031 was resolved at 13:05 UTC on 18 March 2026 [S1][S3].

- Cited: on call timeline INC 2026 031, Incident Report INC-2026-031
- **Grade:** correct (no false conflict)

## co_simple_04 · simple · expected: answer

**Question:** What was fraud-scorer's p99 latency at the morning peak after model v7 went live?

**Reference:** About 6 seconds, up from about 250 ms.

**Gold documents:** Postmortem INC-2026-031: Duplicate Card Charges

### simple: answered

After fraud-scorer model v7 went live, its p99 latency reached about 6 seconds during the morning peak [S1][S2].

- Cited: fraud-scorer Service Documentation, Postmortem INC-2026-031: Duplicate Card Charges
- **Grade:** correct

### agent: answered

After model v7 went live, fraud-scorer's p99 latency at the morning peak reached 6 seconds [S1][S2].

- Cited: fraud-scorer Service Documentation, Postmortem INC-2026-031: Duplicate Card Charges
- **Grade:** correct

## co_simple_05 · simple · expected: answer

**Question:** How long does the NovaPay server SDK wait before it retries a payment that timed out?

**Reference:** 15 minutes.

**Gold documents:** NovaPay Server SDK - Retry Behaviour

### simple: answered

The SDK places the timed-out request in a local retry queue and sends it again after 15 minutes [S1].

- Cited: NovaPay Server SDK - Retry Behaviour
- **Grade:** correct

### agent: answered

The NovaPay server SDK waits 15 minutes before retrying a payment request that resulted in a timeout (HTTP 504) [S1][S3].

- Cited: NovaPay Server SDK - Retry Behaviour, Postmortem INC-2026-031: Duplicate Card Charges
- **Grade:** correct

## co_multi_01 · multi_doc · expected: answer

**Question:** Which two March changes combined to cause the duplicate charges, what did each one change, and who owned each change?

**Reference:** CHG-0412 (9 March, owner: Payments team, Tomas Novak) lowered payments-api's idempotency-key TTL from 24 hours to 10 minutes; CHG-0419 (17 March, owner: Fraud team, Priya Raman) deployed fraud-scorer model v7, which was much slower under load.

**Gold documents:** Production change log - March 2026, Postmortem INC-2026-031: Duplicate Card Charges

### simple: partial

CHG-0412 (9 March) lowered the idempotency-key TTL in payments-api from 24 hours to 10 minutes [S2]. CHG-0419 (17 March) deployed fraud-scorer model v7, which was much slower under load [S2].

- Cited: Postmortem INC-2026-031: Duplicate Card Charges
- Missing: who owned each change
- **Grade:** partly correct (both changes and what each changed are right; owners missing (it says so))

### agent: partial

The incident was caused by the combination of CHG-0412 and CHG-0419 [S5]. CHG-0412 lowered the idempotency-key TTL in payments-api from 24 hours to 10 minutes [S5]. CHG-0419 deployed fraud-scorer model v7, which was much slower under load [S5].

- Cited: Postmortem INC-2026-031: Duplicate Card Charges
- Missing: who owned each change
- **Grade:** partly correct (same: owners missing)

## co_multi_02 · multi_doc · expected: answer

**Question:** Why did the SDK's automatic retry charge cards a second time instead of being recognised as the same payment?

**Reference:** The SDK retries after 15 minutes, but since CHG-0412 payments-api kept idempotency keys for only 10 minutes, so the key had expired and the retry was treated as a new payment.

**Gold documents:** NovaPay Server SDK - Retry Behaviour, Production change log - March 2026

### simple: answered

The SDK retried payment requests after 15 minutes using the original idempotency key [S1], but a recent change (CHG-0412) had lowered the idempotency-key TTL in payments-api from 24 hours to 10 minutes [S2]. Because the key had already expired by the time the retry arrived, payments-api treated the retry as a new payment and charged the card again [S2].

- Cited: NovaPay Server SDK - Retry Behaviour, Postmortem INC-2026-031: Duplicate Card Charges
- **Grade:** correct (15-minute retry vs 10-minute key lifetime, key expired, new payment)

### agent: answered

The SDK retried the payment after a timeout, but the idempotency-key TTL in payments-api had been lowered from 24 hours to 10 minutes [S4]. Because the key had already expired by the time the retry occurred, the system treated the retry as a brand-new payment and charged the card a second time [S4].

- Cited: Postmortem INC-2026-031: Duplicate Card Charges
- **Grade:** partly correct (expired key is right, but it leaves out the 15-minute retry delay that explains why)

## co_multi_03 · multi_doc · expected: answer

**Question:** Why were customers charged even though api-gateway returned an error to the merchant? Compare the gateway's timeout with how long payments-api waits for fraud-scorer.

**Reference:** api-gateway gives up after 5 seconds and returns HTTP 504, but payments-api waits up to 8 seconds for fraud-scorer and still completed the capture, so the charge went through.

**Gold documents:** api gateway service doc, payments-api service documentation

### simple: answered

Customers were charged because api-gateway has a timeout of 5 seconds, whereas payments-api waits up to 8 seconds for the fraud-scorer service [S1][S3][S5]. When fraud-scorer v7 suffered high latency under load, api-gateway gave up and returned a 504 error to the merchant after 5 seconds, while payments-api continued processing and successfully captured the payment [S1].

- Cited: Postmortem INC-2026-031: Duplicate Card Charges, api gateway service doc
- **Grade:** correct

### agent: answered

Customers were charged because api-gateway timed out and returned HTTP 504 to the merchant while payments-api continued processing and successfully captured the payment [S2]. The merchant's SDK later retried the request, but because the idempotency-key TTL had been lowered to 10 minutes, payments-api treated the retry as a new payment and charged the card a second time [S2]. Regarding timeouts, the api-gateway timeout is set to 5 seconds, whereas the payments-api waits up to 8 seconds for fraud-scorer [S1].

- Cited: Postmortem INC-2026-031: Duplicate Card Charges
- **Grade:** correct (extra detail about the retry is fine)

## co_multi_04 · multi_doc · expected: answer

**Question:** Which runbook explains how to undo the change that slowed down fraud-scorer, and which change request introduced that change?

**Reference:** The fraud-scorer model rollback runbook: set FRAUD_MODEL_VERSION to the previous version and restart the fraud-scorer pods one at a time. The change was CHG-0419, which deployed model v7 on 17 March 2026; it was rolled back on 18 March as CHG-0422.

**Gold documents:** Runbook: roll back the fraud-scorer model, Production change log - March 2026

### simple: insufficient

(no answer text)

- Cited: (nothing)
- Missing: No document is close enough to the question.
- **Grade:** wrong (blocked by the similarity gate; no answer)

### agent: answered

The change that slowed down fraud-scorer was introduced by change request CHG-0419 [S2], and the runbook explaining how to undo it is the fraud-scorer rollback runbook [S2] (titled "Runbook: roll back the fraud-scorer model") [S6].

- Cited: fraud-scorer Service Documentation, Runbook: roll back the fraud-scorer model
- **Grade:** correct (right runbook and CHG-0419)

## co_multi_05 · multi_doc · expected: answer

**Question:** Which follow-up actions were agreed after INC-2026-031, and which of the two causing changes does each one address?

**Reference:** CHG-0412 (idempotency-key TTL): AI-1 raise the TTL above the longest SDK retry window (done 18 March, CHG-0423, 48 hours), AI-5 a CAB check of client retry behaviour for idempotency changes, AI-6 update the payments-api documentation. CHG-0419 (fraud-scorer model v7): AI-2 load-test fraud-scorer models at peak traffic before release. Neither change directly: AI-3 make the api-gateway and payments-api fraud-scorer timeouts consistent, AI-4 alert on the HTTP 504 rate for POST /v1/payments.

**Gold documents:** INC-2026-031 action item tracker, Production change log - March 2026

### simple: answered

Following INC-2026-031, several follow-up actions were agreed: load-testing fraud-scorer models at peak traffic before release (addressed by CHG-0419) [S2][S3][S5][S6]; raising the idempotency-key TTL above the longest SDK retry window (addressed by CHG-0412) [S1][S3]; making the api-gateway timeout and payments-api timeout for fraud-scorer consistent (addressed by CHG-0419 and the timeouts mentioned in [S6]) [S3][S6]; adding an alert on the rate of HTTP 504 for POST /v1/payments (addressed by the 504 errors from CHG-0419) [S3][S6]; adding a CAB check of client retry behavior for idempotency changes (addressed by CHG-0412) [S3][S5][S6]; and updating the payments-api service documentation after CHG-0412 and CHG-0423 [S1][S3].

- Cited: on call timeline INC 2026 031, Email to Affected Merchants: Duplicate Charges on 18 March, INC-2026-031 action item tracker, Change Advisory Board Notes - March 2026, Postmortem INC-2026-031: Duplicate Card Charges
- **Grade:** partly correct (all six actions listed, four mapped right; AI-3 and AI-4 are tied to CHG-0419, but they address neither change directly)

### agent: partial

The agreed follow-up actions (action items) following INC-2026-031 include raising the idempotency-key TTL (AI-1), load-testing fraud-scorer models before release (AI-2), making gateway and payments timeouts consistent (AI-3), adding an alert on HTTP 504 rates (AI-4), adding a CAB check for client retry behavior on idempotency changes (AI-5), and updating service documentation (AI-6) [S4]. Finance and Support also agreed to refund every duplicate charge [S3].

- Cited: Incident Report INC-2026-031, INC-2026-031 action item tracker
- Missing: which of the two causing changes each follow-up action addresses
- **Grade:** partly correct (all six actions listed, but not mapped to the two changes (it says so))

## co_conflict_01 · contradiction · expected: flag_conflict

**Question:** How many card payments were charged twice during the 18 March incident?

**Reference:** Sources disagree: 1,284 card payments charged twice (incident report, postmortem) vs 1,317 duplicate charges refunded (finance refund memo).

**Gold documents:** Incident Report INC-2026-031, Memo: Refunds for INC-2026-031

### simple: partial

Sources disagree on the exact number of card payments charged twice, stating either 1,284 card payments [S1][S2] or 1,317 duplicate charges [S7].

- Cited: Incident Report INC-2026-031, Postmortem INC-2026-031: Duplicate Card Charges, Memo: Refunds for INC-2026-031
- Conflict, number of duplicate card payments and total amount: 1,284 card payments were charged twice, totaling EUR 186,420 (S1, S2) vs 1,317 duplicate charges were refunded, totaling EUR 191,236.50 (S7)
- **Grade:** correct (1,284 vs 1,317) · **Conflict flagged:** yes

### agent: answered

During the 18 March incident, 1,284 card payments were charged twice [S1][S2].

- Cited: Incident Report INC-2026-031, Postmortem INC-2026-031: Duplicate Card Charges
- **Grade:** partly correct (1,284 is right per the incident report, but the finance memo's 1,317 is hidden) · **Conflict flagged:** no

## co_conflict_02 · contradiction · expected: flag_conflict

**Question:** What was the total amount of the duplicate charges in euros?

**Reference:** Sources disagree: EUR 186,420 (incident report, postmortem) vs EUR 191,236.50 (finance refund memo).

**Gold documents:** Incident Report INC-2026-031, Memo: Refunds for INC-2026-031

### simple: partial

The incident report and postmortem state that 1,284 duplicate charges totaled EUR 186,420 [S1][S3]. However, the finance operations memo states that 1,317 duplicate charges were refunded for a total of EUR 191,236.50 [S2].

- Cited: Incident Report INC-2026-031, Memo: Refunds for INC-2026-031, Postmortem INC-2026-031: Duplicate Card Charges
- Conflict, total number and amount of duplicate charges: 1,284 card payments were charged twice, totaling EUR 186,420 (S1, S3) vs 1,317 duplicate charges were refunded, totaling EUR 191,236.50 (S2)
- Missing: Runbook S8 does not provide the answer to the question.
- **Grade:** correct (EUR 186,420 vs EUR 191,236.50) · **Conflict flagged:** yes

### agent: answered

The sources disagree on the total amount: the incident report and postmortem state it was EUR 186,420 [S2][S3], whereas the finance memo states that a total of EUR 191,236.50 was refunded [S1].

- Cited: Memo: Refunds for INC-2026-031, Incident Report INC-2026-031, Postmortem INC-2026-031: Duplicate Card Charges
- Conflict, total amount of duplicate charges: EUR 186,420 (S2, S3) vs EUR 191,236.50 (S1)
- **Grade:** correct · **Conflict flagged:** yes

## co_conflict_03 · contradiction · expected: flag_conflict

**Question:** How long does payments-api keep idempotency keys?

**Reference:** Sources disagree: the payments-api service doc (last updated 20 February) says 24 hours, but the change log shows CHG-0412 cut it to 10 minutes on 9 March and CHG-0423 raised it to 48 hours on 18 March, so it is now 48 hours.

**Gold documents:** payments-api service documentation, Production change log - March 2026

### simple: answered

Initially, idempotency keys were kept for 24 hours [S1]. The TTL was later lowered to 10 minutes [S2][S7], and subsequently raised to 48 hours [S5].

- Cited: payments-api service documentation, Postmortem INC-2026-031: Duplicate Card Charges, INC-2026-031 action item tracker, Change Advisory Board Notes - March 2026
- Conflict, duration of payments-api idempotency key TTL: Idempotency keys are kept for 24 hours. (S1) vs The idempotency-key TTL in payments-api was lowered from 24 hours to 10 minutes on 9 March (CHG-0412). (S2, S7) vs The idempotency-key TTL was raised to 48 hours on 18 March (CHG-0423). (S5)
- **Grade:** correct (24 hours vs 10 minutes vs 48 hours) · **Conflict flagged:** yes

### agent: answered

The duration payments-api keeps idempotency keys has changed over time: original documentation stated 24 hours [S1], a change (CHG-0412) lowered it to 10 minutes [S2][S6], and an emergency change (CHG-0423) subsequently raised it to 48 hours [S7][S8].

- Cited: payments-api service documentation, Postmortem INC-2026-031: Duplicate Card Charges, Change Advisory Board Notes - March 2026, Production change log - March 2026, INC-2026-031 action item tracker
- Conflict, payments-api idempotency key TTL duration: Idempotency keys are kept for 24 hours. (S1) vs CHG-0412 lowered the idempotency-key TTL in payments-api from 24 hours to 10 minutes. (S2, S6) vs The idempotency-key TTL was raised from 10 minutes to 48 hours (CHG-0423). (S7, S8)
- **Grade:** correct · **Conflict flagged:** yes

## co_conflict_04 · contradiction · expected: flag_conflict

**Question:** When did the 18 March payment incident start?

**Reference:** Sources disagree: 09:40 UTC (incident report, postmortem, on-call timeline) vs 10:15 UTC (status page).

**Gold documents:** Incident Report INC-2026-031, NovaPay status page - 18 March 2026

### simple: partial

The first duplicate charge was captured at 09:40 UTC [S1][S3][S8], while the NovaPay status page states the incident started at 10:15 UTC [S5].

- Cited: Incident Report INC-2026-031, on call timeline INC 2026 031, NovaPay status page - 18 March 2026, Postmortem INC-2026-031: Duplicate Card Charges
- Conflict, When the incident or duplicate charges started: Duplicate charges started at 09:40 UTC (S1, S3, S8) vs The incident started at 10:15 UTC (S5)
- Missing: A single agreed-upon start time for the incident due to conflicting sources.
- **Grade:** correct (09:40 vs 10:15) · **Conflict flagged:** yes

### agent: answered

The sources disagree on the exact start time of the payment incident on 18 March 2026: incident reports state that latency started rising at 09:25 UTC and the first duplicate charge was captured at 09:40 UTC [S1][S3], whereas the status page states that payments were captured twice starting at 10:15 UTC [S5].

- Cited: Incident Report INC-2026-031, on call timeline INC 2026 031, NovaPay status page - 18 March 2026
- Conflict, When the payment incident or duplicate charges started on 18 March: The fraud-scorer latency started rising at 09:25 UTC, and the first duplicate charge was captured at 09:40 UTC. (S1, S3) vs Some card payments were captured twice starting at 10:15 UTC. (S5)
- **Grade:** correct · **Conflict flagged:** yes

## co_conflict_05 · contradiction · expected: flag_conflict

**Question:** How long did the 18 March incident last from start to resolution?

**Reference:** Depends on the start time: 3 h 25 min from 09:40 UTC (incident report) or 2 h 50 min from 10:15 UTC (status page); resolved at 13:05 UTC.

**Gold documents:** Incident Report INC-2026-031, NovaPay status page - 18 March 2026

### simple: answered

The 18 March incident lasted from 09:25 to 13:05 UTC, spanning a duration of three hours and forty minutes [S3][S5].

- Cited: on call timeline INC 2026 031, Incident Report INC-2026-031
- **Grade:** partly correct (3 h 40 min from 09:25 is supported, but the 10:15 status-page start is missing) · **Conflict flagged:** no

### agent: answered

The 18 March incident (INC-2026-031) began with latency starting at 09:25 UTC (or with the first duplicate charge at 09:40 UTC) and was resolved at 13:05 UTC, lasting a total of three hours and forty minutes (or three hours and twenty-five minutes from the first duplicate charge) [S2][S4].

- Cited: Incident Report INC-2026-031, on call timeline INC 2026 031
- **Grade:** partly correct (gives 3 h 25 min from 09:40, but misses the 10:15 / 2 h 50 min side) · **Conflict flagged:** no

## co_none_01 · unanswerable · expected: insufficient

**Question:** How much Redis memory did the idempotency-key change (CHG-0412) save?

**Reference:** Not in the documents (planted missing fact).

**Gold documents:** (none)

### simple: partial

CHG-0412 reduced the idempotency-key TTL in Redis from 24 hours to 10 minutes to reduce Redis memory use [S1]. However, the sources do not state the exact amount of Redis memory that was saved.

- Cited: Production change log - March 2026
- Missing: the exact amount of Redis memory saved by CHG-0412
- **Grade:** partly correct (text correctly says the amount is missing, but status is partial instead of insufficient)

### agent: partial

Change CHG-0412 reduced the idempotency-key TTL in Redis from 24 hours to 10 minutes to reduce memory use, but the sources do not specify the exact amount of memory saved [S2][S3].

- Cited: Change Advisory Board Notes - March 2026, Production change log - March 2026
- Missing: The exact amount of Redis memory saved by CHG-0412
- **Grade:** partly correct (same: right text, wrong status)

## co_none_02 · unanswerable · expected: insufficient

**Question:** Was a regulator notified about incident INC-2026-031?

**Reference:** Not in the documents (planted missing fact).

**Gold documents:** (none)

### simple: insufficient

(no answer text)

- Cited: (nothing)
- Missing: whether a regulator was notified about incident INC-2026-031
- **Grade:** correct

### agent: insufficient

(no answer text)

- Cited: (nothing)
- Missing: Whether a regulator was notified about incident INC-2026-031.
- **Grade:** correct

## co_none_03 · unanswerable · expected: insufficient

**Question:** What caused NovaPay's payment outage in February 2026?

**Reference:** Not in the documents: they describe no February outage.

**Gold documents:** (none)

### simple: partial

The sources do not mention an outage in February 2026, but describe an incident on 18 March 2026 [S4][S8]. That incident was caused by two changes in March: a lowered idempotency-key TTL and a slower fraud-scorer model under load, which led to HTTP 504 timeouts and subsequent duplicate card charges when retried [S8].

- Cited: Incident Report INC-2026-031, Postmortem INC-2026-031: Duplicate Card Charges
- Missing: any payment outage in February 2026
- **Grade:** partly correct (says there's no February outage, but status is partial and it adds the March incident's cause)

### agent: partial

The sources do not mention an outage in February 2026, but describe an incident on 18 March 2026 where rising fraud-scorer latency caused timeouts (HTTP 504) for successful payments, which the server SDK then retried and captured twice [S2][S4].

- Cited: Email to Affected Merchants: Duplicate Charges on 18 March, Incident Report INC-2026-031
- Missing: Any NovaPay payment outage occurring in February 2026
- **Grade:** partly correct (same: right text, wrong status)

## co_none_04 · unanswerable · expected: insufficient

**Question:** What fee does NovaPay charge merchants per card transaction?

**Reference:** Not in the documents.

**Gold documents:** (none)

### simple: insufficient

(no answer text)

- Cited: (nothing)
- Missing: The fee that NovaPay charges merchants per card transaction is not mentioned in the provided sources.
- **Grade:** correct

### agent: insufficient

(no answer text)

- Cited: (nothing)
- Missing: The provided sources do not state the fee NovaPay charges merchants per card transaction.
- **Grade:** correct

## co_none_05 · unanswerable · expected: insufficient

**Question:** Which programming language is payments-api written in?

**Reference:** Not in the documents.

**Gold documents:** (none)

### simple: insufficient

(no answer text)

- Cited: (nothing)
- Missing: The programming language that payments-api is written in
- **Grade:** correct

### agent: insufficient

(no answer text)

- Cited: (nothing)
- Missing: The programming language that payments-api is written in is not specified in the sources.
- **Grade:** correct