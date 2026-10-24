# Optimized GLM-4.7 T01 — one reported live smoke test

Recorded 2026-10-24 from maintainer evidence supplied in chat. The actual test
timestamp and complete raw trace/response were not supplied. The repository
agent did not execute the live test or independently retrieve platform usage.
The [structured record](../evaluations/records/v2.1/2026-10-24-glm47-t01-smoke.json)
preserves the exact reported metrics and evidence limits.

Application: **MyTech v2.1 — GLM47 Optimized TEST**. Both main LLM nodes use
`glm-4.7` with shortened prompts. Reported KB: **MyTech v2.1 — TEST Knowledge**.

Input: `I need a laptop under ¥6,000 for gaming.`

Reported result: **PASS**, recommending MECHREVO Jiaolong 16K at RMB 4,999,
Laptop/Gaming, within the RMB 6,000 hard budget; `clarification_needed=false` and
a KB citation present. The reported label corresponds to Master ID `LAP-005`.
The full raw public JSON/source string was not supplied, so this is a reported
smoke verdict rather than an independent machine validation of that live reply.

| Metric | State Extraction | Recommendation AI Chat #2 |
| --- | ---: | ---: |
| Model | glm-4.7 | glm-4.7 |
| Latency | 12.33 s | 21.69 s |
| Input tokens | 1,645 | 3,731 |
| Output tokens | 112 | 719 |
| AI credits | 0.2205 | 0.7326 |

Total workflow latency: **34.45 s**. Combined AI-node credits: **0.9531**.
Other workflow nodes account for approximately **0.43 s**. The two AI-node
debits are not an independently verified platform-wide bill; that total remains
unavailable. Do not double-count node debits with an aggregate meter delta.

Historical reference only: a previous longer-prompt GLM-4.7 run took approximately
36.5 s; the working mixed DeepSeek/GLM configuration previously took approximately
5.05 s for a single-product recommendation. These are unpaired observations
without fully controlled input/history/cache/queue/revision conditions. They
do not establish statistical improvement, causal prompt savings or model superiority.

The shortened workflow produced a reported valid, budget-compliant recommendation
but still took about 34 seconds. **Prompt shortening has not demonstrated a
meaningful latency improvement. No complete six-request A/B experiment has been
performed.** The optimized application remains experimental and Original remains
the university AIEP default. The six future A/B result rows stay `NOT_RUN`; this
independent T01 observation does not fill them. No additional requests are authorized.
