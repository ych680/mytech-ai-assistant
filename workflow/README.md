# MyTech FastGPT Workflow

This folder contains the FastGPT workflow configuration used by MyTech, a grounded RAG-based electronic product recommendation assistant.

## Workflow Architecture

The workflow combines LLM-based state extraction with deterministic validation and knowledge-base retrieval.

### Main Pipeline

1. **Workflow Start**
   - Receives the user's message.

2. **State Extraction**
   - Extracts product category, budget, main usage, follow-up intent, and request scope.

3. **State Normalization & Guard**
   - Normalizes extracted state.
   - Preserves contextual follow-up requests.
   - Applies deterministic category validation.

4. **Scope Router**
   - Routes supported, unsupported, help, and unrelated requests.

5. **Conversation State Update**
   - Persists the normalized active requests for subsequent conversation turns.

6. **Clarification Router**
   - Requests missing information when category, budget, or main usage is incomplete.

7. **Retrieval Query Builder**
   - Builds state-aware retrieval queries using the active request, previous recommendations, and follow-up intent.

8. **Knowledge Retrieval**
   - Retrieves relevant product evidence from the MyTech knowledge base.

9. **Recommendation Assistant**
   - Generates grounded product recommendations using retrieved evidence and the active conversation state.

10. **Response Validation & Normalization**
    - Validates product identity, category, price, hard-budget constraints, source consistency, and follow-up behavior.
    - Produces the normalized JSON response consumed by the frontend.

11. **Validation Router**
    - Sends valid recommendations to the final response path.
    - Routes invalid outputs to a safe fallback response.

12. **Recommendation State Update**
    - Stores validated recommendations for contextual follow-up requests such as cheaper, more expensive, or alternative options.

The valid path ends at **Final Structured Response**. Dedicated branches handle missing-information clarification, unsupported categories, help/greetings, unrelated requests, and validation fallback. Conversation variables are associated with the FastGPT `chatId` supplied by the backend.

### Retrieval and Validation

Knowledge retrieval supplies the product evidence used by the recommendation model. The workflow's static validation catalogue then checks product identity, category, exact reference price, source, hard budgets, active-request consistency, duplicate categories, and follow-up constraints. Retrieval and validation have separate roles: the catalogue is a rule-checking layer, not a replacement for RAG retrieval.

The Node.js backend and browser apply further response checks before rendering. Their checks are not identical to the workflow's; details are in the [main README](../README.md#system-architecture). Validation enforces defined rules but does not verify every generated explanation.

### Structured Response

Terminal branches use the same top-level response fields:

```json
{
  "answer": "Here is a reference recommendation.",
  "recommendations": [
    {
      "category": "Laptop",
      "recommended_product": "Lenovo Xiaoxin 14 (2025, Ryzen 7 H255, 16GB/512GB)",
      "price": 5799,
      "reason": "Suitable for study and office use.",
      "source": "Lenovo Official Store"
    }
  ],
  "next_step": "Tell me if you need another option.",
  "clarification_needed": false
}
```

This is an illustrative contract example, not a recorded model response. `recommendations` may be empty for clarification or no-result responses. The application contract allows an omitted source; the recommendation workflow checks source consistency against its catalogue.

## Workflow Screenshots

These screenshots show the workflow architecture from an earlier snapshot; they are not evidence of every current model setting.

### State Extraction and Scope Routing

![Workflow Overview 1](workflow-overview-1.png)

### Clarification and RAG Recommendation Pipeline

![Workflow Overview 2](workflow-overview-2.png)

### Validation and Response Flow

![Workflow Overview 3](workflow-overview-3.png)

## Workflow Configuration

The exported FastGPT workflow is available here:

[mytech-fastgpt-workflow.json](mytech-fastgpt-workflow.json)

The workflow export includes the node configuration, prompts, routing logic, JavaScript validation logic, state variables, and workflow connections.

## Knowledge Base Setup

The FastGPT export does not package the linked knowledge base itself.

After importing the workflow:

1. Create a FastGPT knowledge base.
2. Import [MyTech_Product_Knowledge_v1.md](../knowledge/MyTech_Product_Knowledge_v1.md).
3. Open the **Knowledge Retrieval** node.
4. Bind the newly created knowledge base to that node.
5. Re-select the models described below, then save and publish the workflow.

The provided knowledge file contains 27 reference products across nine categories. Keep its product facts consistent with the [local validation dataset](../mytech_v1_product_dataset.json) and the workflow's static validation catalogue if adapting the prototype.

## Model Configuration

The synchronized export retains the following intended model selections:

| Node | Model |
|---|---|
| State Extraction | `glm-5.3-flash` |
| Clarification Assistant | `glm-5.3-flash` |
| Recommendation Assistant | `deepseek-v4.1-flash` |

Account-specific `modelId` values are empty, so imported nodes may require model re-selection. Compatible model availability depends on the target FastGPT deployment. If substituting a model, verify the routing, recommendation, and structured-output behavior in that environment.

## Important Notes

- Product prices are fixed reference prices for this prototype and are not live retailer prices.
- The user's budget is treated as a hard maximum.
- Recommendations must remain within the requested product category.
- Product facts must be grounded in retrieved knowledge-base evidence.
- The validation layer rejects inconsistent, over-budget, or unsupported recommendations.
- API credentials are not included in the exported workflow.

## Portfolio Export Sanitization

Deployment-specific identifiers have been intentionally removed from the current portable export. AI-node `modelId` values are empty; **Knowledge Retrieval** has `datasets: []`, and its dataset-description ID is `REPLACE_AFTER_IMPORT`. Node IDs and internal connections are preserved.

After importing the workflow into your own FastGPT deployment:

1. Re-select the intended models listed above, or compatible models available in your deployment.
2. Create or import your own knowledge base.
3. Bind that knowledge base to the **Knowledge Retrieval** node.
4. Save and publish the workflow in your own environment.

No API credentials, private deployment URLs, application IDs, or original knowledge-base identifiers are included in this portfolio export.
