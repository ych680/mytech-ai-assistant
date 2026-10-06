import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { dirname, extname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { isPlainObject, normaliseOutput, parseFastGptResponse, validateOutput } from "./mytech_response.mjs";

const APP_DIRECTORY = dirname(fileURLToPath(import.meta.url));
const PORT = Number.parseInt(process.env.PORT || "8787", 10);
const FASTGPT_API_KEY = process.env.FASTGPT_API_KEY?.trim() || "";
const FASTGPT_API_URL = process.env.FASTGPT_API_URL?.trim() || "";
const FASTGPT_APP_ID = process.env.FASTGPT_APP_ID?.trim() || "";
const FASTGPT_URL_IS_VALID = isAllowedFastGptUrl(FASTGPT_API_URL);
const MAXIMUM_REQUEST_BYTES = 1_000_000;
const MAXIMUM_CHAT_ID_LENGTH = 128;

const HTML_FILE = "MyTech_Chatbot_v2.html";
const DATASET_FILE = "mytech_v1_product_dataset.json";
const SYSTEM_PROMPT_FILE = "mytech_v1_system_prompt.txt";
const STATIC_FILES = new Set([HTML_FILE, DATASET_FILE, SYSTEM_PROMPT_FILE]);

function isAllowedFastGptUrl(value) {
  try {
    const url = new URL(value);
    if (url.protocol === "https:") return true;
    return url.protocol === "http:"
      && (url.hostname === "127.0.0.1" || url.hostname === "localhost" || url.hostname === "::1");
  } catch {
    return false;
  }
}

const [productDataset, systemPrompt] = await Promise.all([
  readFile(join(APP_DIRECTORY, DATASET_FILE), "utf8").then(JSON.parse),
  readFile(join(APP_DIRECTORY, SYSTEM_PROMPT_FILE), "utf8")
]);

const supportedCategories = productDataset.supported_categories;
const productByName = new Map(productDataset.products.map((product) => [product.product, product]));

// FastGPT returns this contract from every terminal workflow branch. The source
// field remains optional exactly as defined by the approved MyTech specification.
const MODEL_OUTPUT_SCHEMA = {
  type: "object",
  properties: {
    answer: { type: "string" },
    recommendations: {
      type: "array",
      items: {
        type: "object",
        properties: {
          category: { type: "string", enum: supportedCategories },
          recommended_product: { type: "string" },
          price: { type: "number", minimum: 0 },
          reason: { type: "string" },
          source: { type: "string" }
        },
        required: ["category", "recommended_product", "price", "reason"],
        additionalProperties: false
      }
    },
    next_step: { type: "string" },
    clarification_needed: { type: "boolean" }
  },
  required: ["answer", "recommendations", "next_step", "clarification_needed"],
  additionalProperties: false
};

function sendJson(response, statusCode, body) {
  const payload = JSON.stringify(body);
  response.writeHead(statusCode, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": Buffer.byteLength(payload),
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff"
  });
  response.end(payload);
}

function sendText(response, statusCode, content, contentType) {
  response.writeHead(statusCode, {
    "Content-Type": contentType,
    "Content-Length": Buffer.byteLength(content),
    "Cache-Control": "no-store",
    "Content-Security-Policy": "default-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY"
  });
  response.end(content);
}

async function readJsonBody(request) {
  const chunks = [];
  let totalBytes = 0;
  for await (const chunk of request) {
    totalBytes += chunk.length;
    if (totalBytes > MAXIMUM_REQUEST_BYTES) throw new Error("REQUEST_TOO_LARGE");
    chunks.push(chunk);
  }
  try {
    return JSON.parse(Buffer.concat(chunks).toString("utf8"));
  } catch {
    throw new Error("INVALID_JSON_BODY");
  }
}

function cleanString(value, maximumLength) {
  return typeof value === "string" ? value.slice(0, maximumLength) : "";
}

function sanitiseChatId(value) {
  const chatId = cleanString(value, MAXIMUM_CHAT_ID_LENGTH).trim();
  if (!/^[A-Za-z0-9][A-Za-z0-9_-]{7,127}$/.test(chatId)) {
    throw new Error("INVALID_CHAT_ID");
  }
  return chatId;
}

function sanitiseHistory(history) {
  if (!Array.isArray(history)) return [];
  return history
    .slice(-16)
    .filter((item) => isPlainObject(item) && (item.role === "user" || item.role === "assistant"))
    .map((item) => ({ role: item.role, content: cleanString(item.content, 12_000) }))
    .filter((item) => item.content);
}

function sanitiseConstraintMap(value, kind) {
  const constraints = {};
  if (!isPlainObject(value)) return constraints;
  supportedCategories.forEach((category) => {
    if (kind === "budget" && Number.isFinite(value[category]) && value[category] > 0) {
      constraints[category] = Math.round(value[category]);
    }
    if (kind === "usage" && typeof value[category] === "string" && value[category].length <= 80) {
      constraints[category] = value[category];
    }
  });
  return constraints;
}

function sanitiseContext(value) {
  if (!isPlainObject(value) || !Array.isArray(value.activeRequests)) return { activeRequests: [] };
  return {
    activeRequests: value.activeRequests.slice(0, 9).map((request) => ({
      category: supportedCategories.includes(request?.category) ? request.category : null,
      budget: Number.isFinite(request?.budget) && request.budget > 0 ? Math.round(request.budget) : null,
      usage: cleanString(request?.usage, 80) || null,
      lastRecommendation: productByName.has(request?.lastRecommendation) ? request.lastRecommendation : null
    })).filter((request) => request.category)
  };
}

async function callFastGPT({ message, chatId, signal }) {
  const apiResponse = await fetch(FASTGPT_API_URL, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${FASTGPT_API_KEY}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      appId: FASTGPT_APP_ID,
      chatId,
      stream: false,
      detail: false,
      messages: [{ role: "user", content: message }]
    }),
    signal
  });

  const body = await apiResponse.json().catch(() => ({}));
  if (!apiResponse.ok) {
    console.error(`FastGPT request failed with HTTP ${apiResponse.status}.`);
    const error = new Error("MODEL_REQUEST_FAILED");
    error.upstreamStatus = apiResponse.status;
    throw error;
  }

  return parseFastGptResponse(body);
}

async function createValidatedResponse(payload) {
  const message = cleanString(payload.message, 8000).trim();
  if (!message) throw new Error("INVALID_MESSAGE");

  const chatId = sanitiseChatId(payload.chatId);
  sanitiseContext(payload.context);
  const budgets = sanitiseConstraintMap(payload.budgetConstraints, "budget");
  const usages = sanitiseConstraintMap(payload.usageConstraints, "usage");

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 60_000);
  let output;
  try {
    output = await callFastGPT({ message, chatId, signal: controller.signal });
  } finally {
    clearTimeout(timeout);
  }

  output = normaliseOutput(output);
  const finalErrors = validateOutput(output, budgets, usages, { productByName, supportedCategories });
  if (!finalErrors.length) return output;

  const error = new Error("MODEL_OUTPUT_VALIDATION_FAILED");
  error.validationErrors = finalErrors;
  throw error;
}

async function handleStaticRequest(request, response, pathname) {
  const requestedFile = pathname === "/" ? HTML_FILE : decodeURIComponent(pathname.slice(1));
  if (!STATIC_FILES.has(requestedFile)) {
    sendJson(response, 404, { error: "NOT_FOUND", message: "Not found." });
    return;
  }

  const content = await readFile(join(APP_DIRECTORY, requestedFile));
  const contentTypes = {
    ".html": "text/html; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".txt": "text/plain; charset=utf-8"
  };
  sendText(response, 200, content, contentTypes[extname(requestedFile)] || "application/octet-stream");
}

const server = createServer(async (request, response) => {
  try {
    const url = new URL(request.url || "/", `http://${request.headers.host || "localhost"}`);

    if (request.method === "GET" && url.pathname === "/api/health") {
      const ready = Boolean(FASTGPT_API_KEY) && FASTGPT_URL_IS_VALID && Boolean(FASTGPT_APP_ID);
      sendJson(response, 200, {
        ready,
        provider: "fastgpt",
        appId: ready ? FASTGPT_APP_ID : null
      });
      return;
    }

    if (request.method === "POST" && url.pathname === "/api/mytech") {
      if (!FASTGPT_API_KEY || !FASTGPT_URL_IS_VALID || !FASTGPT_APP_ID) {
        sendJson(response, 503, {
          error: "MODEL_NOT_CONFIGURED",
          message: "Set FASTGPT_API_KEY and valid FASTGPT_API_URL and FASTGPT_APP_ID values on the server."
        });
        return;
      }

      const payload = await readJsonBody(request);
      const output = await createValidatedResponse(payload);
      sendJson(response, 200, { output, provider: "fastgpt", appId: FASTGPT_APP_ID });
      return;
    }

    if (request.method === "GET") {
      await handleStaticRequest(request, response, url.pathname);
      return;
    }

    sendJson(response, 405, { error: "METHOD_NOT_ALLOWED", message: "Method not allowed." });
  } catch (error) {
    if (error.message === "REQUEST_TOO_LARGE") {
      sendJson(response, 413, { error: error.message, message: "Request body is too large." });
      return;
    }
    if (["INVALID_JSON_BODY", "INVALID_MESSAGE", "INVALID_CHAT_ID"].includes(error.message)) {
      sendJson(response, 400, { error: error.message, message: "Invalid request." });
      return;
    }
    if (error.message === "MODEL_OUTPUT_VALIDATION_FAILED") {
      console.error("Model output validation failed:", error.validationErrors);
      sendJson(response, 502, {
        error: error.message,
        message: "The model response could not be validated safely."
      });
      return;
    }
    if (error.name === "AbortError") {
      sendJson(response, 504, { error: "MODEL_TIMEOUT", message: "The FastGPT request timed out." });
      return;
    }
    if (["EMPTY_MODEL_OUTPUT", "MODEL_OUTPUT_NOT_JSON", "MODEL_REQUEST_FAILED"].includes(error.message)) {
      sendJson(response, 502, {
        error: error.message,
        message: "The FastGPT workflow did not return a usable structured response."
      });
      return;
    }

    console.error(error);
    sendJson(response, 502, { error: "MODEL_REQUEST_FAILED", message: "The secure FastGPT request failed." });
  }
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`MyTech v2 is available at http://127.0.0.1:${PORT}`);
  if (!FASTGPT_API_KEY) console.log("FastGPT is not configured: set FASTGPT_API_KEY before starting the server.");
  if (!FASTGPT_URL_IS_VALID) console.log("FastGPT is not configured: FASTGPT_API_URL must use HTTPS.");
  if (!FASTGPT_APP_ID) console.log("FastGPT is not configured: set FASTGPT_APP_ID before starting the server.");
});
