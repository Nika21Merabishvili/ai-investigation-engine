# Error analysis

29 of the 90 answers (45 questions × 2 modes) failed at least one check: gold answer not in the answer, recall@5 = 0, a wrong abstention, a missed conflict, citation accuracy below 1, or a hand grade of partly correct or wrong. I picked 10 that each show one failure type clearly, from both modes and both question sets, and checked each in the raw answers; the similarity values come from re-running simple mode's search without the LLM, which returned the same top 8 as the saved run.

| id | mode | group | what happened |
| --- | --- | --- | --- |
| hp_bridge_05 | simple | Retrieval miss | Neither gold page (Kool Kojak, The Lorax) was in the top 8, which were other animated films (The Lion King, Toy Story, Moana ...); the LLM rightly said "insufficient". Agent mode found The Lorax with its first search. |
| hp_comparison_07 | agent | Retrieval miss | Neither player's page came back: "Wayne Black nationality" returned Lil Wayne, Meek Mill and others. It answered only half ("Marray is British", from a Wimbledon page that does say so), status partial. |
| co_conflict_01 | agent | Retrieval miss | One search, then it answered: 5 chunks, 3 of them from the same postmortem, none from the finance memo. It said 1,284 and flagged no conflict; the memo's 1,317 was never seen. |
| co_multi_05 | simple | Wrong answer despite good sources | Action tracker (rank 3) and change log (rank 8) were both there. It listed all six actions but tied AI-3 and AI-4 to CHG-0419, though they address neither change directly. |
| hp_comparison_10 | simple | Wrong answer despite good sources | Both gold pages were there (ranks 2 and 7). It said Manchester Orchestra's member count "is not stated", but that page names four members; status partial. Agent mode counted them and got it right. |
| hp_bridge_09 | agent | Bad citation | Both gold pages came first in its only search, but the answer had no valid [S#] marker, so finalize() withheld it as "insufficient". Simple mode answered correctly (Captain John Underhill) from the same two chunks. The withheld text is not saved. |
| co_simple_01 | simple | Bad citation | Right date (17 March 2026, from the fraud-scorer doc), but it also cites the incident report, which has no deploy date; citation accuracy 0.33. Second cause: the gold change log was not in the top 8. |
| co_multi_04 | simple | Wrong abstention | Gate: the runbook was at rank 6 but came from keyword search only, so it had no dense score. The best dense score in the top 8 was 0.597 ("Fake field goal"), below 0.62, so the gate blocked it. Agent mode answered correctly. |
| hp_bridge_10 | simple | Wrong abstention | LLM: both gold pages were at ranks 1 and 2. Nightmares is a 1983 film, and Estevez's page names "the 1983 hit movie The Outsiders", yet the LLM said no other 1983 film was mentioned. |
| co_none_01 | agent | Wrong abstention | Status: unanswerable question. Its text says the sources don't give the memory saved, yet the status is "partial", not "insufficient". Same in simple mode, and for co_none_03 in both modes. |

### Retrieval miss (3 of 10)

Simple mode searches once, with the whole question. Keyword search matches any single word of the query, so parts of names pull in other pages (Lil Wayne for "Wayne Black"), and dense search tends to find pages about the general topic rather than the named people, like the famous animated films in hp_bridge_05. Agent mode can search again, but each search returns only 5 chunks and the prompt tells it to stop once the passages answer the question, so in co_conflict_01 it stopped as soon as it found one number. Not implemented yet, but what I would change: return 8 chunks per agent search with at most 2 from the same document, and for questions about a count, amount or time, force one more search for other sources of that number before answering.

### Wrong answer despite good sources (2 of 10)

Here retrieval worked and the model's reasoning fell short. The prompt says "Never guess", and the model seems to treat anything it has to work out itself as missing: it would not count the four names on the Manchester Orchestra page. When it does work something out, nothing checks it: the action tracker mostly does not say which change an action belongs to, and the model guessed wrong for AI-3 and AI-4. Not implemented yet: one prompt line saying that counting, comparing or subtracting values from the sources is allowed if the step is shown, and for matching questions ("which action goes with which change") a rule to quote the sentence that links each pair, or say the link is not stated.

### Bad citation (2 of 10)

finalize() only checks that each [S#] id exists; nothing checks that the cited chunk says what the sentence claims, so extra sources slip in, like the incident report in co_simple_01. finalize() also withholds the whole answer when no valid marker is left, which turned hp_bridge_09 (agent) into "insufficient" although both gold pages were in hand, and because the withheld text is not saved we cannot see what went wrong with the markers. Not every low citation score is a real error: in hp_comparison_04 (simple), hp_comparison_07 and co_multi_05 (agent) the cited page does support the sentence but is not on the gold list. Not implemented yet: before withholding, ask the model once more to add markers (as ask_llm_json() already does for unreadable JSON) and save the withheld text; and drop a citation when a date or number in the sentence does not appear in the cited chunk.

### Wrong abstention (3 of 10)

Two different steps cause this. The gate looks only at dense similarity, but in all three gate blocks that had a gold page in the top 8 (co_multi_04, hp_comparison_07, hp_bridge_13), that page came from keyword search only, so the gate judged the question by unrelated pages such as "Fake field goal". The LLM sets the status itself and errs both ways: it gave up in hp_bridge_10 with both facts in front of it, and on unanswerable questions it says "partial" when it finds related background, even though its own text says the asked fact is missing. Not implemented yet: gate on the fused hybrid score, or let a keyword-only chunk in the top 3 pass the gate; add a prompt rule that related background does not make an answer "partial"; and add a check that sets "insufficient" when the answer says the sources do not give the fact asked for.
