# MyTech v2 — Grounded RAG Product Recommendation Assistant

MyTech v2 is an electronic product recommendation assistant developed as part of postgraduate AI coursework. The current implementation combines a browser interface, a Node.js backend with server-side API key handling, and a published FastGPT workflow with grounded RAG retrieval, conversation-state handling, deterministic validation, and structured JSON responses.

## Architecture

```text
Browser Frontend
        ↓
Node.js Server
        ↓
FastGPT Published Workflow
        ↓
State Extraction & Routing
        ↓
Knowledge Base Retrieval (RAG)
        ↓
Grounded Recommendation Generation
        ↓
Deterministic Validation
        ↓
Structured JSON Response
        ↓
Product Card Rendering
```

The browser calls the same-origin `/api/mytech` endpoint. The server calls FastGPT and validates the structured response; the browser validates it again before rendering product cards. The FastGPT API key remains server-side and must never be exposed to the browser, HTML, or client-side JavaScript.

Each conversation uses a stable, non-secret `chatId` so follow-up requests can reuse conversation context.

## Demo

### Chatbot Interface

The frontend uses a minimal editorial-style interface with starter prompts, conversation reset, generation status, and structured product-card rendering.

![MyTech Chatbot UI](docs/screenshots/mytech-chatbot-ui.png)

### Multi-product Recommendation

MyTech can process multiple product requests in a single message while keeping each product's category, budget, and usage requirements separate.

Example:

> I need a laptop under RMB 6000 for study and a mouse under RMB 300 for gaming.

![MyTech Multi-product Recommendation Demo](docs/screenshots/mytech-multi-product-demo.png)

## Supported Features

- Nine product categories: Laptop, Desktop, Smartphone, Tablet, Headphones, Monitor, Smartwatch, Mouse, and Keyboard.
- Multi-turn conversation and clarification of missing or ambiguous requirements.
- Multiple product requests with separate category, budget, and usage constraints.
- Hard-budget protection.
- Cheaper / more expensive / alternative follow-up requests.
- State-aware retrieval query generation.
- Grounded RAG retrieval through the FastGPT Knowledge Base / Dataset Search.
- Structured JSON output and validated product-card rendering.
- Deterministic category, price, source, and follow-up validation.
- Safe fallback responses for invalid generated output.
- Restart / conversation reset with a fresh FastGPT `chatId`.

## FastGPT Workflow

The portfolio FastGPT workflow is included in:

```text
workflow/mytech-fastgpt-workflow.json
```

The workflow contains the node configuration, prompts, routing logic, conversation-state handling, JavaScript guards, retrieval query generation, recommendation generation, validation logic, and workflow connections.

Detailed workflow documentation and screenshots are available in:

```text
workflow/README.md
```

### Main Workflow

```text
Workflow Start
      ↓
State Extraction
      ↓
State Normalization & Guard
      ↓
Scope Router
      ↓
Conversation State Update
      ↓
Clarification Router
      ├── Missing information
      │        ↓
      │  Clarification Assistant
      │
      └── Complete request
               ↓
        Retrieval Query Builder
               ↓
        Knowledge Retrieval
               ↓
        Recommendation Assistant
               ↓
        Response Validation & Normalization
               ↓
        Validation Router
          ├── Valid
          │     ↓
          │ Recommendation State Update
          │     ↓
          │ Final Structured Response
          │
          └── Invalid
                ↓
          Validation Fallback Response
```

The workflow also contains dedicated branches for unsupported product categories, help / greeting requests, and unrelated requests.

## Grounded RAG Knowledge Base

The FastGPT Knowledge Base is the grounded product-fact retrieval source used by the published workflow.

The portfolio knowledge-base source is included in:

```text
knowledge/MyTech_Product_Knowledge_v1.md
```

The knowledge base contains 27 reference products across nine supported categories. Each product record keeps the product name, category, reference price, usage, key features, and source together for retrieval.

The exported FastGPT workflow does not package the linked knowledge base itself. After importing the workflow:

1. Create a FastGPT knowledge base.
2. Import `knowledge/MyTech_Product_Knowledge_v1.md`.
3. Open the **Knowledge Retrieval** node.
4. Bind the newly created knowledge base.
5. Save and publish the workflow.

## Retrieval and Local References

The **FastGPT Knowledge Base** is the current grounded product-fact retrieval source used by the published workflow.

`mytech_v1_product_dataset.json` remains a required local validation/reference dataset containing 27 products. The application checks recommendations against it and uses its product details to render cards.

`mytech_v1_system_prompt.txt` remains a required local runtime/reference file loaded during current initialization. Keep both local files alongside the server and HTML file.

## Validation and Safety

MyTech does not rely only on LLM output.

The workflow applies deterministic checks for:

- supported product categories
- product identity
- category consistency
- exact reference prices
- source consistency
- hard-budget compliance
- duplicate-category recommendations
- cheaper / more expensive / alternative follow-up constraints

FastGPT content is parsed as structured JSON with:

- `answer`
- `recommendations[]`
- `next_step`
- `clarification_needed`

Invalid, empty, malformed, timed-out, or failed responses display a safe error state without rendering unvalidated product cards.

Prices are fixed RMB reference prices for this coursework prototype; live retailer prices and stock availability are not supported.

## Structured Response Contract

Successful recommendation responses follow this general structure:

```json
{
  "answer": "string",
  "recommendations": [
    {
      "category": "Laptop",
      "recommended_product": "Exact product name",
      "price": 5799,
      "reason": "Short grounded recommendation reason.",
      "source": "Reference source"
    }
  ],
  "next_step": "string",
  "clarification_needed": false
}
```

For multiple product requests, the `recommendations` array can contain one validated recommendation for each separate request.

## Model Configuration

The portfolio workflow uses **Qwen-turbo** for:

- state extraction
- clarification
- grounded recommendation generation

Model availability may vary between FastGPT deployments.

## Project Structure

```text
MyTech_v2/
├── docs/
│   └── screenshots/
│       ├── mytech-chatbot-ui.png
│       └── mytech-multi-product-demo.png
├── knowledge/
│   └── MyTech_Product_Knowledge_v1.md
├── workflow/
│   ├── mytech-fastgpt-workflow.json
│   ├── README.md
│   ├── workflow-overview-1.png
│   ├── workflow-overview-2.png
│   └── workflow-overview-3.png
├── MyTech_Chatbot_v2.html
├── mytech_v2_server.mjs
├── mytech_v1_product_dataset.json
├── mytech_v1_system_prompt.txt
├── .env.example
├── .gitignore
└── README.md
```

Local `.env` files are intentionally excluded from version control.

## Project Files

- `MyTech_Chatbot_v2.html` — browser interface, conversation state, response validation, and product-card rendering.
- `mytech_v2_server.mjs` — Node.js server, server-side FastGPT connection, and response validation.
- `mytech_v1_product_dataset.json` — required local product validation/reference dataset.
- `mytech_v1_system_prompt.txt` — required local runtime/reference prompt file.
- `knowledge/MyTech_Product_Knowledge_v1.md` — RAG knowledge-base source.
- `workflow/mytech-fastgpt-workflow.json` — exported FastGPT workflow configuration.
- `workflow/README.md` — workflow architecture, screenshots, and import instructions.
- `docs/screenshots/` — portfolio screenshots showing the chatbot interface and multi-product recommendation behavior.
- `.env.example` — environment configuration template.
- `.gitignore` — excludes local environment files, dependencies, logs, and generated files.

## Setup

1. Install Node.js 20.6+.
2. Copy `.env.example` to `.env` in the project directory.
3. Fill in your own FastGPT configuration:

   ```text
   FASTGPT_API_KEY
   FASTGPT_API_URL
   FASTGPT_APP_ID
   ```

4. Import `workflow/mytech-fastgpt-workflow.json` into FastGPT.
5. Create a knowledge base using `knowledge/MyTech_Product_Knowledge_v1.md` and bind it to the **Knowledge Retrieval** node.
6. Run:

   ```bash
   node --env-file=.env mytech_v2_server.mjs
   ```

7. Open [http://127.0.0.1:8787](http://127.0.0.1:8787).

Never commit your real `.env` file.

## Testing

The project has been tested for:

- normal single-product recommendations
- contextual follow-up requests
- clarification of missing information
- unsupported product categories
- hard-budget enforcement
- multi-product requests
- structured JSON rendering
- conversation reset and state handling

## Prototype Limitations

MyTech is currently a local classroom / portfolio prototype.

- Product prices are fixed RMB reference prices rather than live retailer prices.
- Product availability and stock are not checked in real time.
- The knowledge base contains a deliberately limited reference dataset.
- Public deployment would require additional protections such as authentication, rate limiting, monitoring, and production-grade secret management.

## Security

No real API keys or `.env` files should ever be committed to this repository.

Deployment-specific FastGPT endpoints, application IDs, model IDs, and knowledge-base identifiers are intentionally omitted from the public portfolio version. Configure your own values through `.env` and re-bind the model / knowledge base after importing the workflow.

The `.gitignore` configuration excludes local environment files, while `.env.example` documents the required configuration without containing credentials.

## Project Status

**MyTech v2 — Portfolio Workflow Snapshot**

The current portfolio version includes:

- FastGPT workflow export
- grounded RAG knowledge base
- contextual conversation state
- state-aware retrieval
- deterministic category and budget guards
- structured response validation
- browser-based product recommendation interface
