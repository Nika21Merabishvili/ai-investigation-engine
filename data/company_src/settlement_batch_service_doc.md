title: settlement-batch Service Documentation
format: docx
author: Ana Beridze
date: 2026-03-23

# settlement-batch service documentation

Owner: Finance Engineering. Last updated: 23 March 2026 by Ana Beridze (Finance Operations).

## Purpose

settlement-batch pays merchants their net balance once a day. It reads balances from ledger-service, subtracts fees and refunds, and sends payout instructions to the bank.

## Schedule

The batch runs every night at 02:00 UTC. It moved from 01:00 to 02:00 UTC on 5 March 2026 (CHG-0409) so that late acquirer files are included.

## Holds

Finance can hold the payout of a single merchant for one run. Every hold is logged in ledger-service with a reason code.

## INC-2026-031

On 19 March 2026 the payouts of the 212 merchants affected by INC-2026-031 were held, so that duplicate charges would not be paid out before they were refunded. The held payouts were paid on 20 March 2026, after all refunds were completed.
