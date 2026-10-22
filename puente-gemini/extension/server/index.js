#!/usr/bin/env node
// Servidor MCP local que consulta Gemini (API de Google) desde Claude Desktop y Cowork.
// No tiene dependencias: habla MCP por stdio (JSON-RPC 2.0, un mensaje por línea)
// y usa el fetch integrado de Node 18+.
"use strict";

const fs = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");
const readline = require("node:readline");

const SERVER_INFO = { name: "gemini", title: "Gemini", version: "1.0.0" };
const SUPPORTED_PROTOCOLS = ["2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"];
const API_BASE = "https://generativelanguage.googleapis.com/v1beta";
const FALLBACK_MODEL = "gemini-3.1-pro-preview";
const REQUEST_TIMEOUT_MS = 120_000;
const PROGRESS_EVERY_MS = 10_000;
const MAX_INLINE_BYTES = 18 * 1024 * 1024; // la API acepta peticiones de hasta ~20 MB
const MAX_FILES = 10;

// Los PDF e imágenes viajan como datos binarios; los formatos de texto se leen y se envían como texto.
const BINARY_TYPES = {
  ".pdf": "application/pdf",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
  ".heic": "image/heic",
  ".heif": "image/heif",
};
const TEXT_EXTENSIONS = new Set([".txt", ".md", ".csv", ".tsv", ".json", ".xml", ".html", ".htm", ".rtf", ".log"]);
const BINARY_MIME = new Set(Object.values(BINARY_TYPES));

class UserError extends Error {}

// Claude Desktop sustituye ${user_config.x}; si el campo quedó vacío puede llegar el texto literal.
function configValue(name) {
  const value = (process.env[name] || "").trim();
  return value.startsWith("${") ? "" : value;
}

function apiKey() {
  const key = configValue("GEMINI_API_KEY") || configValue("GOOGLE_API_KEY");
  if (!key) {
    throw new UserError(
      "Falta la clave de la API de Gemini. Créala en https://aistudio.google.com/apikey y pégala en " +
        "Claude Desktop → Configuración → Extensiones → Gemini.",
    );
  }
  return key;
}

function normalizeModel(value) {
  const model = String(value || "").trim().replace(/^models\//, "");
  if (!model) return "";
  if (!/^[A-Za-z0-9._-]+$/.test(model)) throw new UserError(`"${model}" no es un nombre de modelo válido.`);
  return model;
}

function defaultModel() {
  return normalizeModel(configValue("GEMINI_MODEL")) || FALLBACK_MODEL;
}

// ---------- API de Gemini ----------

// AbortSignal.any no existe antes de Node 20.3; se combina a mano por compatibilidad.
function withTimeout(signal) {
  const timeout = AbortSignal.timeout(REQUEST_TIMEOUT_MS);
  if (!signal) return timeout;
  if (typeof AbortSignal.any === "function") return AbortSignal.any([timeout, signal]);
  const controller = new AbortController();
  for (const s of [timeout, signal]) {
    if (s.aborted) controller.abort(s.reason);
    else s.addEventListener("abort", () => controller.abort(s.reason), { once: true });
  }
  return controller.signal;
}

async function geminiFetch(url, init, context = {}) {
  let res;
  try {
    res = await fetch(url, {
      ...init,
      headers: { "Content-Type": "application/json", "x-goog-api-key": apiKey(), ...(init.headers || {}) },
      signal: withTimeout(init.signal),
    });
  } catch (err) {
    if (err instanceof UserError) throw err;
    if (err.name === "TimeoutError") {
      throw new UserError("Gemini tardó más de 2 minutos en responder. Prueba con una pregunta más corta o con un modelo Flash.");
    }
    if (err.name === "AbortError") throw new UserError("La consulta se canceló.");
    throw new UserError(`No pude conectar con la API de Gemini (${err.cause?.code || err.message}). Revisa tu conexión a internet.`);
  }
  const raw = await res.text();
  let data = null;
  try {
    data = raw ? JSON.parse(raw) : null;
  } catch {
    data = null;
  }
  if (!res.ok) throw new UserError(describeApiError(res.status, data, raw, context));
  return data;
}

function describeApiError(status, data, raw, { model } = {}) {
  const error = data?.error || {};
  const message = error.message || raw.slice(0, 300) || "sin detalle";
  const reasons = (error.details || []).map((d) => d.reason).filter(Boolean);
  if (reasons.includes("API_KEY_INVALID") || /API key not valid/i.test(message)) {
    return "Google dice que la clave de API no es válida. Crea una nueva en https://aistudio.google.com/apikey y actualízala en la configuración de la extensión.";
  }
  if (status === 401 || status === 403) return `Google rechazó la clave (permiso denegado): ${message}`;
  if (status === 404) {
    return `El modelo "${model || "?"}" no existe o tu clave no tiene acceso a él. Usa list_gemini_models para ver los disponibles. Detalle: ${message}`;
  }
  if (status === 429) {
    return `Llegaste al límite de uso de la API de Gemini. Espera un momento o revisa tu plan y facturación en AI Studio. Detalle: ${message}`;
  }
  if (status >= 500) return `Gemini no está disponible en este momento (HTTP ${status}). Intenta de nuevo en unos segundos.`;
  return `Error de la API de Gemini (HTTP ${status}): ${message}`;
}

async function listModels() {
  const models = [];
  let pageToken = "";
  do {
    const url = `${API_BASE}/models?pageSize=1000${pageToken ? `&pageToken=${encodeURIComponent(pageToken)}` : ""}`;
    const data = await geminiFetch(url, { method: "GET" });
    for (const m of data?.models || []) {
      const id = String(m.name || "").replace(/^models\//, "");
      if (!id.startsWith("gemini") || !(m.supportedGenerationMethods || []).includes("generateContent")) continue;
      models.push({
        id,
        display_name: m.displayName || id,
        description: m.description || "",
        input_token_limit: m.inputTokenLimit ?? null,
        output_token_limit: m.outputTokenLimit ?? null,
      });
    }
    pageToken = data?.nextPageToken || "";
  } while (pageToken);
  models.sort((a, b) => a.id.localeCompare(b.id));
  return { default_model: defaultModel(), models };
}

// ---------- Archivos adjuntos ----------

function expandHome(p) {
  return p === "~" || p.startsWith("~/") || p.startsWith("~\\") ? path.join(os.homedir(), p.slice(1)) : p;
}

async function partsFromPaths(filePaths, budget) {
  const parts = [];
  for (const raw of filePaths) {
    const full = path.resolve(expandHome(String(raw)));
    const name = path.basename(full);
    const ext = path.extname(full).toLowerCase();
    let info;
    try {
      info = await fs.stat(full);
    } catch {
      throw new UserError(`No encuentro el archivo ${full}.`);
    }
    if (!info.isFile()) throw new UserError(`${full} no es un archivo.`);
    budget.use(info.size, name);
    if (BINARY_TYPES[ext]) {
      const data = await fs.readFile(full);
      parts.push({ text: `Archivo adjunto: ${name}` }, { inline_data: { mime_type: BINARY_TYPES[ext], data: data.toString("base64") } });
    } else if (TEXT_EXTENSIONS.has(ext)) {
      parts.push({ text: `Contenido del archivo ${name}:\n\n${await fs.readFile(full, "utf8")}` });
    } else {
      throw new UserError(`No puedo enviar ${name} a Gemini. Formatos admitidos: PDF, imágenes (PNG, JPG, WebP, HEIC) y texto (TXT, MD, CSV, JSON, HTML). Guarda los Word como PDF.`);
    }
  }
  return parts;
}

function partsFromAttachments(attachments, budget) {
  const parts = [];
  for (const a of attachments) {
    const name = String(a?.name || "adjunto");
    const mime = String(a?.mime_type || "").toLowerCase();
    const data = String(a?.data_base64 || "");
    if (!data) throw new UserError(`El adjunto ${name} llegó vacío.`);
    budget.use(Math.floor((data.length * 3) / 4), name);
    if (BINARY_MIME.has(mime)) {
      parts.push({ text: `Archivo adjunto: ${name}` }, { inline_data: { mime_type: mime, data } });
    } else if (mime.startsWith("text/") || mime === "application/json" || mime === "application/xml") {
      parts.push({ text: `Contenido del archivo ${name}:\n\n${Buffer.from(data, "base64").toString("utf8")}` });
    } else {
      throw new UserError(`No puedo enviar ${name} (${mime || "tipo desconocido"}) a Gemini. Usa PDF, imágenes o texto.`);
    }
  }
  return parts;
}

function byteBudget() {
  let used = 0;
  return {
    use(bytes, name) {
      used += bytes;
      if (used > MAX_INLINE_BYTES) throw new UserError(`Los adjuntos superan el límite de 18 MB por consulta (al sumar ${name}).`);
    },
  };
}

// ---------- ask_gemini ----------

function buildContents(history, prompt, extraParts) {
  const contents = [];
  for (const turn of history) {
    const text = typeof turn?.text === "string" ? turn.text : "";
    if (!text.trim()) continue;
    const role = turn.role === "model" || turn.role === "assistant" ? "model" : "user";
    if (!contents.length && role === "model") continue; // Gemini exige que la conversación empiece con el usuario
    const last = contents[contents.length - 1];
    if (last && last.role === role) last.parts.push({ text });
    else contents.push({ role, parts: [{ text }] });
  }
  const parts = [...extraParts, { text: prompt }];
  const last = contents[contents.length - 1];
  if (last && last.role === "user") last.parts.push(...parts);
  else contents.push({ role: "user", parts });
  return contents;
}

function readAnswer(data) {
  const candidate = data?.candidates?.[0];
  if (!candidate) {
    const blocked = data?.promptFeedback?.blockReason;
    throw new UserError(blocked ? `Gemini bloqueó la pregunta (motivo: ${blocked}).` : "Gemini no devolvió ninguna respuesta.");
  }
  const text = (candidate.content?.parts || [])
    .filter((p) => typeof p.text === "string" && !p.thought)
    .map((p) => p.text)
    .join("");
  const finish = candidate.finishReason || "";
  if (!text.trim()) throw new UserError(`Gemini no devolvió texto (motivo: ${finish || "desconocido"}).`);

  const grounding = candidate.groundingMetadata || {};
  const seen = new Set();
  const sources = [];
  for (const chunk of grounding.groundingChunks || []) {
    const web = chunk.web;
    if (!web?.uri || seen.has(web.uri)) continue;
    seen.add(web.uri);
    sources.push({ title: web.title || web.uri, uri: web.uri });
  }
  const usage = data.usageMetadata || {};
  return {
    text,
    finish_reason: finish,
    sources,
    search_queries: grounding.webSearchQueries || [],
    usage: {
      prompt_tokens: usage.promptTokenCount ?? null,
      output_tokens: usage.candidatesTokenCount ?? null,
      total_tokens: usage.totalTokenCount ?? null,
    },
  };
}

async function askGemini(args, signal) {
  const prompt = typeof args.prompt === "string" ? args.prompt : "";
  if (!prompt.trim()) throw new UserError("Escribe la pregunta para Gemini en el campo prompt.");
  const history = Array.isArray(args.history) ? args.history.slice(-200) : [];
  const filePaths = Array.isArray(args.file_paths) ? args.file_paths : [];
  const attachments = Array.isArray(args.attachments) ? args.attachments : [];
  if (filePaths.length + attachments.length > MAX_FILES) throw new UserError(`Puedes adjuntar hasta ${MAX_FILES} archivos por consulta.`);

  const budget = byteBudget();
  const extraParts = [...partsFromAttachments(attachments, budget), ...(await partsFromPaths(filePaths, budget))];
  const model = normalizeModel(args.model) || defaultModel();

  const body = { contents: buildContents(history, prompt, extraParts) };
  if (typeof args.system === "string" && args.system.trim()) body.systemInstruction = { parts: [{ text: args.system }] };
  if (args.google_search === true) body.tools = [{ google_search: {} }];
  const generationConfig = {};
  if (typeof args.temperature === "number" && args.temperature >= 0 && args.temperature <= 2) generationConfig.temperature = args.temperature;
  if (Number.isInteger(args.max_output_tokens) && args.max_output_tokens > 0) generationConfig.maxOutputTokens = args.max_output_tokens;
  if (Object.keys(generationConfig).length) body.generationConfig = generationConfig;

  const data = await geminiFetch(
    `${API_BASE}/models/${encodeURIComponent(model)}:generateContent`,
    { method: "POST", body: JSON.stringify(body), signal },
    { model },
  );
  return { model, ...readAnswer(data) };
}

function answerAsText(answer) {
  const lines = [answer.text];
  if (answer.finish_reason === "MAX_TOKENS") lines.push("\n[La respuesta se cortó por el límite de longitud.]");
  if (answer.sources.length) {
    lines.push("\nFuentes que citó Gemini (búsqueda de Google):");
    for (const s of answer.sources) lines.push(`- ${s.title}: ${s.uri}`);
  }
  lines.push(`\n(Respondió ${answer.model}.)`);
  return lines.join("\n");
}

// ---------- Definición de herramientas ----------

const TOOLS = [
  {
    name: "ask_gemini",
    title: "Preguntar a Gemini",
    description:
      "Envía una pregunta a Gemini (API de Google, con la clave del usuario) y devuelve su respuesta. " +
      "Úsala cuando el usuario pida consultar a Gemini, una segunda opinión de otro modelo o contrastar una respuesta. " +
      "Admite historial de conversación, instrucciones de sistema, búsqueda en Google con fuentes y archivos (PDF, imágenes, texto).",
    inputSchema: {
      type: "object",
      properties: {
        prompt: { type: "string", description: "La pregunta o instrucción para Gemini." },
        history: {
          type: "array",
          description: "Turnos anteriores de la conversación, del más antiguo al más reciente.",
          items: {
            type: "object",
            properties: { role: { type: "string", enum: ["user", "model"] }, text: { type: "string" } },
            required: ["role", "text"],
          },
        },
        system: { type: "string", description: "Instrucciones de sistema para Gemini (tono, idioma, reglas)." },
        model: { type: "string", description: "ID del modelo, por ejemplo gemini-3.1-pro-preview. Si se omite, se usa el configurado en la extensión." },
        google_search: { type: "boolean", description: "Si es true, Gemini busca en Google y devuelve las fuentes que usó." },
        temperature: { type: "number", minimum: 0, maximum: 2 },
        max_output_tokens: { type: "integer", minimum: 1 },
        file_paths: {
          type: "array",
          items: { type: "string" },
          description: "Rutas de archivos locales para adjuntar (PDF, PNG, JPG, WebP, HEIC, TXT, MD, CSV, JSON, HTML). Máximo 18 MB en total.",
        },
        attachments: {
          type: "array",
          description: "Archivos ya codificados en base64.",
          items: {
            type: "object",
            properties: { name: { type: "string" }, mime_type: { type: "string" }, data_base64: { type: "string" } },
            required: ["mime_type", "data_base64"],
          },
        },
      },
      required: ["prompt"],
    },
    outputSchema: {
      type: "object",
      properties: {
        model: { type: "string" },
        text: { type: "string" },
        finish_reason: { type: "string" },
        sources: { type: "array", items: { type: "object", properties: { title: { type: "string" }, uri: { type: "string" } } } },
        search_queries: { type: "array", items: { type: "string" } },
        usage: { type: "object" },
      },
      required: ["model", "text"],
    },
    annotations: { readOnlyHint: true, openWorldHint: true },
  },
  {
    name: "list_gemini_models",
    title: "Ver modelos de Gemini",
    description: "Lista los modelos de Gemini disponibles para la clave configurada y cuál se usa por defecto.",
    inputSchema: { type: "object", properties: {} },
    outputSchema: {
      type: "object",
      properties: { default_model: { type: "string" }, models: { type: "array", items: { type: "object" } } },
      required: ["default_model", "models"],
    },
    annotations: { readOnlyHint: true, openWorldHint: true },
  },
];

async function callTool(name, args, signal) {
  if (name === "ask_gemini") {
    const answer = await askGemini(args, signal);
    return { content: [{ type: "text", text: answerAsText(answer) }], structuredContent: answer };
  }
  if (name === "list_gemini_models") {
    const result = await listModels();
    const text = [`Modelo por defecto: ${result.default_model}`, ...result.models.map((m) => `- ${m.id} (${m.display_name})`)].join("\n");
    return { content: [{ type: "text", text }], structuredContent: result };
  }
  throw new UserError(`No existe la herramienta ${name}.`);
}

// ---------- Transporte MCP por stdio ----------

const inflight = new Map();

function send(message) {
  process.stdout.write(`${JSON.stringify(message)}\n`);
}

function startProgress(token) {
  if (token === undefined) return () => {};
  let tick = 0;
  const timer = setInterval(() => {
    tick += 1;
    send({ jsonrpc: "2.0", method: "notifications/progress", params: { progressToken: token, progress: tick, message: "Esperando a Gemini…" } });
  }, PROGRESS_EVERY_MS);
  return () => clearInterval(timer);
}

async function handle(msg) {
  const { id, method, params = {} } = msg;
  if (typeof method !== "string") return; // respuestas a peticiones nuestras: no enviamos ninguna
  const isNotification = id === undefined || id === null;

  if (isNotification) {
    if (method === "notifications/cancelled") inflight.get(params.requestId)?.abort();
    return;
  }

  if (method === "initialize") {
    const requested = params.protocolVersion;
    send({
      jsonrpc: "2.0",
      id,
      result: {
        protocolVersion: SUPPORTED_PROTOCOLS.includes(requested) ? requested : SUPPORTED_PROTOCOLS[0],
        capabilities: { tools: { listChanged: false } },
        serverInfo: SERVER_INFO,
        instructions: "Usa ask_gemini para consultar a Gemini con la clave del usuario y list_gemini_models para ver los modelos disponibles.",
      },
    });
    return;
  }
  if (method === "ping") {
    send({ jsonrpc: "2.0", id, result: {} });
    return;
  }
  if (method === "tools/list") {
    send({ jsonrpc: "2.0", id, result: { tools: TOOLS } });
    return;
  }
  if (method === "tools/call") {
    const controller = new AbortController();
    inflight.set(id, controller);
    const stopProgress = startProgress(params._meta?.progressToken);
    try {
      const result = await callTool(params.name, params.arguments || {}, controller.signal);
      if (!controller.signal.aborted) send({ jsonrpc: "2.0", id, result });
    } catch (err) {
      if (!(err instanceof UserError)) console.error(err);
      const text = err instanceof UserError ? err.message : `Error inesperado en la extensión de Gemini: ${err.message}`;
      if (!controller.signal.aborted) send({ jsonrpc: "2.0", id, result: { content: [{ type: "text", text }], isError: true } });
    } finally {
      stopProgress();
      inflight.delete(id);
    }
    return;
  }
  send({ jsonrpc: "2.0", id, error: { code: -32601, message: `Método no soportado: ${method}` } });
}

function onLine(line) {
  if (!line.trim()) return;
  let parsed;
  try {
    parsed = JSON.parse(line);
  } catch {
    send({ jsonrpc: "2.0", id: null, error: { code: -32700, message: "JSON inválido" } });
    return;
  }
  for (const msg of Array.isArray(parsed) ? parsed : [parsed]) {
    handle(msg).catch((err) => console.error(err));
  }
}

if (require.main === module) {
  const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
  rl.on("line", onLine);
  rl.on("close", () => process.exit(0));
  console.error(`[gemini] servidor MCP ${SERVER_INFO.version} listo (modelo por defecto: ${defaultModel()})`);
}

module.exports = { buildContents, readAnswer, describeApiError, normalizeModel };
