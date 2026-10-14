# MyTech v2 — User Acceptance Testing (UAT) & Bug Fix Summary

**Project:** MyTech v2 | INT6137  
**Report date:** 12 October 2026  
**Report status:** Final record of the observed UAT and BUG-01 live regression; UX improvements pending  
**Version:** 1.0  
**Code baseline:** `main` at `da6e43de21431a5befed3aebd6489ddc1d9c072a` (post-PR #12 merge)

## 1. Executive Summary

Eight documented manual UAT scenarios reached **PASS** as their final recorded outcomes. Five of the initial six scenarios passed immediately. UAT-06 (missing-information clarification) failed twice with HTTP 502 / `MODEL_OUTPUT_NOT_JSON`, prompting a targeted investigation and a narrowly scoped parsing compatibility fix. Following offline tests, independent review, PR #12, and successful CI, the original UAT-06 input passed a live regression test. Two additional same-session tests (UAT-07 and UAT-08) verified that MyTech retained the laptop category and study/office use case across clarification turns before recommending a product within the stated budget.

**Interpretation:** **8/8** is the final acceptance result for these eight specific scenarios, **not** a statistical accuracy rate, first-attempt pass rate, or guarantee for untested inputs. UAT-06's original two failures remain part of the record.

**Open follow-ups:** UX-01 (redundant, internally worded price note) and UX-02 (generic follow-up prompt wording). These were not modified during BUG-01 remediation.

## 2. System Under Test and Scope

The observed test route was a local Windows browser using the MyTech v2 frontend at `http://127.0.0.1:8787`, backed by a local Node.js server that calls the published school FastGPT workflow through a server-side API connection. Product recommendations use a fixed reference catalogue of **27 products across nine categories**: Laptop, Desktop, Smartphone, Tablet, Headphones, Monitor, Smartwatch, Mouse, and Keyboard. Catalogue prices are classroom reference prices, not verified live retailer quotations.

The response contract uses `answer` (string), `recommendations` (array), `next_step` (string), and `clarification_needed` (boolean). User-visible checks covered basic recommendations, comparison follow-ups, budget constraints, multiple simultaneous product requests, no-match handling, clarification, multi-turn context retention, and final recommendation rendering.

This report records **manual, selected-scenario UAT**. It does not claim formal load, security, accessibility, browser-matrix, or live retail-price testing.

## 3. UAT Scenario Results

*For UAT-01 through UAT-05, input descriptions below are reconstructed from the testing record rather than claimed as verbatim prompts. Exact user text is preserved where available for UAT-06 through UAT-08.*

| ID | Scenario / recorded input | Observed behavior | Final |
|---|---|---|---|
| UAT-01 | Laptop for study/office, maximum RMB 6,000 | Lenovo Xiaoxin 14 (2025, Ryzen 7 H255, 16GB/512GB) recommended at reference price ¥5,799; product card displayed | PASS |
| UAT-02 | Same conversation: request a cheaper laptop | Reported no cheaper matching Laptop in the approved reference catalogue; did not invent an alternative | PASS |
| UAT-03 | Same conversation: raise maximum to RMB 7,000 and request a different laptop | HUAWEI MateBook 14 recommended at ¥6,599; followed updated budget and alternative request | PASS |
| UAT-04 | Fresh conversation: study/office Laptop ≤ RMB 6,000 plus gaming Mouse ≤ RMB 300 | Two independent cards: Lenovo Xiaoxin 14 (¥5,799) and Logitech G304 LIGHTSPEED (¥229) | PASS |
| UAT-05 | Fresh conversation: gaming mouse ≤ RMB 100 | No qualifying product card; mentioned G304 at ¥229 as an option only if the budget increased | PASS |
| UAT-06 | “I'm thinking about buying a laptop. What would you recommend?” | Initially failed twice with generic safe error; after fix asked “What will you mainly use the laptop for?” with no product card | PASS after fix |
| UAT-07 | Same session: “Mostly for studying and office work.” | Remembered the laptop context and asked “What is your budget for the laptop?” | PASS |
| UAT-08 | Same session: “My maximum budget is RMB 6,000.” | Recommended Lenovo Xiaoxin 14 at ¥5,799 with a product card; retained Laptop and Study/Office context | PASS |

**Recorded outcome sequence:** UAT-01–05 PASS; UAT-06 FAIL on two pre-fix attempts, later PASS in one live post-fix regression; UAT-07–08 PASS. The post-fix UAT-06–08 sequence demonstrates clarification → context retention → recommendation for this tested conversation.

## 4. BUG-01 — Clarification JSON Formatting Compatibility

**Status:** Fixed in code; live regression passed for the previously failing scenario.  
**Affected flow:** Missing-information clarification / structured-response parsing.  
**Observed impact:** MyTech displayed a safe error instead of a clarification question; it did **not** display an unsupported recommendation.

### 4.1 Reproduction and evidence

- Exact UAT-06 user input: `I'm thinking about buying a laptop. What would you recommend?`
- Two independent pre-fix attempts produced a safe error message in the MyTech frontend.
- The browser Network response showed **HTTP 502** with `error: MODEL_OUTPUT_NOT_JSON`.
- The Node.js terminal did not display a backend structure-validation error, consistent with the existing non-logging handling for malformed JSON responses.
- The matching FastGPT conversation log correctly extracted `category: Laptop`, `budget: null`, `main_usage: null`, `clarification_needed: true`, and missing fields `budget` and `main_usage`.
- The FastGPT log displayed a structurally valid clarification object with `recommendations: []`. Copying the displayed message from the UI included a Markdown `json` code fence.

**Important evidence limitation:** The historical raw FastGPT API `choices[0].message.content` was **not captured**. The copied UI text does not prove that the raw API response contained the fence; other malformed-output mechanisms were not fully ruled out.

### 4.2 Confirmed technical finding

The original `parseFastGptResponse()` used `JSON.parse()` on the complete FastGPT content without removing Markdown fences. A complete JSON object wrapped in a Markdown code fence would therefore produce `MODEL_OUTPUT_NOT_JSON`. The portable FastGPT workflow export also showed that the recommendation branch normalizes JSON output while the clarification branch does not pass through the same normalization stage. The export may differ from the currently deployed school workflow.

### 4.3 Approved fix and safeguards

PR **#12** introduced narrowly scoped parser compatibility:

- Preserve acceptance of plain valid JSON.
- Additionally accept **one complete lowercase `json` Markdown fence**, including LF or CRLF newlines and optional surrounding whitespace.
- Still parse the entire enclosed JSON document with `JSON.parse()`.
- Continue rejecting surrounding prose, reasoning wrappers, multiple fenced blocks/documents, unsupported fence syntaxes, incomplete JSON, and other malformed output.
- Preserve the original response contract and downstream checks for product identity, category, reference price, source, hard budget, supported usage, and unsupported live-price claims.

Only `mytech_response.mjs` and `tests/response.test.mjs` changed. The frontend, Node.js server integration, product data, knowledge base, and FastGPT workflow were not modified by PR #12.

### 4.4 Review, CI, and deployment record

- **Code review:** Targeted read-only review, minimal fix, and independent code review completed.
- **Feature commit:** `cc589809947a721369dfe5e382d2864f4f25945a`.
- **Pull request:** [MyTech PR #12 — fix: support strictly fenced FastGPT JSON responses](https://github.com/ych680/mytech-ai-assistant/pull/12).
- **Merged to `main`:** 12 October 2026; merge commit `da6e43de21431a5befed3aebd6489ddc1d9c072a`.
- **Offline tests:** 13/13 response tests; 21/21 Node.js tests; 224/224 Python tests; JavaScript syntax checks passed.
- **Dataset/knowledge checks:** 27 products / nine categories validated; 27 knowledge records consistent.
- **GitHub Actions:** Ubuntu, Windows, and macOS cross-platform CI jobs **Success**; Ubuntu Response Tests job **Success**.
- **Local sync:** Windows `main` fast-forwarded to the merge commit; working tree clean; 21/21 Node.js tests and syntax checks passed.
- **Live regression:** The original UAT-06 input returned a normal laptop-usage clarification instead of the prior safe error. UAT-07 and UAT-08 then completed the same conversation successfully.

**Closure language:** BUG-01 can be recorded as **“Fixed — Live Regression Passed”** for the observed UAT-06 path. The precise malformed bytes in the original failed API responses remain unknown, and broader reliability is not established by this single successful regression.

## 5. Outstanding UX Backlog

### UX-01 — Redundant price-reference note and internal-style wording

**Observed UI text:** “Fixed reference prices for the classroom prototype. They are not live retailer quotes. MyTech should describe them as reference prices.”

**Source confirmed in code:** `mytech_v1_product_dataset.json` → `price_note`, rendered by `addStructuredResponse()` in `MyTech_Chatbot_v2.html`. The third sentence is an instruction to the assistant rather than useful user-facing copy. The card already labels its amount as a “Reference price”, and the page footer separately indicates that prices are not live retailer pricing.

**Proposed review direction:** Remove the redundant note from the chat bubble while retaining sufficient visible reference-price disclosure on product cards and the page footer. Preserve the underlying price data. **Not implemented.**

### UX-02 — Generic “cheaper or more expensive” next-step wording

**Observed UI text:** “Would you like a cheaper or more expensive option, or does this meet your needs?”

**Source confirmed in code:** The FastGPT-generated `next_step` field, rendered by the frontend. The phrase is conversational, but can imply that suitable cheaper or more expensive options exist irrespective of the active catalogue and hard budget. In the UAT-08 example, the recommended ¥5,799 laptop is already near the user's ¥6,000 limit.

**Proposed review direction:** Prefer budget- and preference-aware follow-up wording, for example “Does this option meet your needs, or would you like to adjust your budget or preferences?” Verify the live workflow contract and follow-up behavior before any implementation. **Not implemented.**

**Documentation follow-up:** The README's stated Node.js test count predates the five new response tests (16 → 21). Handle this as a separate documentation-only update, not as part of the BUG-01 fix.

## 6. Limitations and Next Actions

1. **Limited manual sample:** Eight selected scenarios cannot establish overall model quality, reliability, or statistical accuracy. The observed outcomes are specific to the test inputs and execution conditions.
2. **Non-deterministic model outputs:** The successful regression does not guarantee identical wording or successful execution on every future run.
3. **Unknown historical raw payload:** The exact FastGPT content responsible for the original UAT-06 failures was not recorded. The parser compatibility gap is confirmed; the historical byte-level root cause is not.
4. **Static product data:** Catalogue prices and source labels are classroom references, not real-time market validation.
5. **Out-of-scope quality dimensions:** No claims are made about performance under load, formal accessibility, security penetration testing, or broad browser/device coverage.
6. **Next phase:** Freeze the passing UAT baseline, conduct a READ-ONLY UX-01/UX-02 review, then approve only targeted changes and follow with offline tests, independent review, PR/CI, and any necessary live UI regression.

## 7. Overall Assessment

**Decision:** The eight selected MyTech v2 UAT scenarios have passed at final acceptance, including successful live regression of the previously failing UAT-06 clarification flow. The relevant parser fix has been reviewed, merged, and verified by cross-platform CI. The completed UAT demonstrates core catalogue-based product selection, hard-budget handling, no-match behavior, multi-item recommendations, and one tested three-turn requirement-collection journey. UX-01 and UX-02 remain open as non-blocking follow-ups.

### Evidence and traceability

- Manual MyTech UAT screenshots and observed responses recorded during the 12 October 2026 session (UAT-06–08) and preceding Round 1 testing notes (UAT-01–05).
- Browser Network record: HTTP 502 / `MODEL_OUTPUT_NOT_JSON` during the original UAT-06 failure.
- FastGPT conversation-log screenshot and copied clarification reply; original API content not preserved.
- GitHub [PR #12](https://github.com/ych680/mytech-ai-assistant/pull/12), merged commit `da6e43de21431a5befed3aebd6489ddc1d9c072a`, and associated successful Actions runs.
- Reviewed implementation sources: `mytech_response.mjs`, `mytech_v2_server.mjs`, `MyTech_Chatbot_v2.html`, `mytech_v1_product_dataset.json`, portable workflow export, and response tests.

---

*Report prepared from observed UAT evidence and verified repository artifacts. It is a project testing record, not an independent certification or an assertion of real-time product prices.*
