# MyTech v2 — Grounded RAG Product Recommendation Assistant

MyTech v2 is an electronic product recommendation assistant developed as part of postgraduate AI coursework. The current Week 04 implementation combines a browser interface, a Node.js backend for this local classroom prototype with server-side API key handling, and a published FastGPT workflow with grounded RAG retrieval.

## Architecture

Browser frontend → Node.js server → FastGPT published workflow → FastGPT Knowledge Base / Dataset Search → grounded structured recommendation response

The browser calls the same-origin `/api/mytech` endpoint. The server calls FastGPT and validates the structured response; the browser validates it again before rendering product cards. The FastGPT API key remains server-side and must never be exposed to the browser, HTML, or client-side JavaScript.

## Supported features

- Nine product categories: Laptop, Desktop, Smartphone, Tablet, Headphones, Monitor, Smartwatch, Mouse, and Keyboard.
- Multi-turn conversation and clarification of missing or ambiguous requirements.
- Multiple product requests with separate category, budget, and usage constraints.
- Hard-budget protection and cheaper / more expensive / alternative follow-ups.
- Grounded RAG retrieval through the FastGPT Knowledge Base / Dataset Search.
- Structured JSON output and validated product-card rendering.
- Restart / conversation reset, clearing local state and generating a new FastGPT `chatId`.

Each conversation uses a stable, non-secret `chatId`. The server sends FastGPT the current user message and that identifier so follow-ups reuse the workflow's conversation context.

## Retrieval and local references

The **FastGPT Knowledge Base** is the current grounded product-fact retrieval source used by the published workflow.

`mytech_v1_product_dataset.json` remains a required local validation/reference dataset containing 27 products. The application checks recommendations against it and uses its product details to render cards.

`mytech_v1_system_prompt.txt` remains a required local runtime/reference file loaded during current initialization. Keep both local files alongside the server and HTML file.

## Project Files

- `MyTech_Chatbot_v2.html` — browser interface, conversation state, response validation, and product-card rendering.
- `mytech_v2_server.mjs` — Node.js server, server-side FastGPT connection, and response validation.
- `mytech_v1_product_dataset.json` — required local product validation/reference dataset.
- `mytech_v1_system_prompt.txt` — required local runtime/reference prompt file.
- `MyTech_v2_FastGPT_Test_Report.pdf` — FastGPT test report.
- `.env.example` — environment configuration template.
- `.gitignore` — excludes local environment files, dependencies, logs, and generated files.

## Setup

1. Install Node.js 20.6+.
2. Copy `.env.example` to `.env` in the project directory.
3. Fill in your own FastGPT configuration: `FASTGPT_API_KEY`, `FASTGPT_API_URL`, and `FASTGPT_APP_ID` for your published workflow with Knowledge Base / Dataset Search configured. Keep `.env` private and out of version control.
4. Run:

   ```bash
   node --env-file=.env mytech_v2_server.mjs
   ```

5. Open [http://127.0.0.1:8787](http://127.0.0.1:8787).

This is a local classroom prototype. Public deployment would require additional protections such as authentication and rate limiting.

## Validation and safety

- FastGPT content is read from `choices[0].message.content` and parsed as JSON with `answer`, `recommendations[]`, `next_step`, and `clarification_needed`.
- Server and browser checks validate products, categories, prices, sources, usage compatibility, and hard budgets. Browser checks also enforce cheaper / more expensive / alternative follow-up constraints before rendering.
- Invalid, empty, malformed, timed-out, or failed responses display a safe error state without rendering unvalidated product cards.
- Prices are fixed RMB reference prices for the coursework prototype; live retailer prices and stock availability are not supported.
