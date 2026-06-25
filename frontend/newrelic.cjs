"use strict";

/**
 * New Relic Node.js Agent Configuration
 *
 * This file uses CommonJS because the New Relic agent loads it via require().
 * It is loaded before the Next.js server starts, so env vars must be
 * available at process level (not from Next.js runtime config).
 *
 * See: https://docs.newrelic.com/docs/apm/agents/nodejs-agent/installation-configuration/nodejs-agent-configuration/
 */

// dotenv is not available in standalone builds — env vars are injected
// by Docker Compose at runtime.

/**
 * @type {import("newrelic").AgentConfig}
 */
exports.config = {
  app_name: [process.env.NEW_RELIC_APP_NAME || "Indic Book Metadata Extractor"],
  license_key: process.env.NEW_RELIC_LICENSE_KEY || "",

  // Hybrid OTel mode — relies on Next.js's native OpenTelemetry spans
  // instead of New Relic's own instrumentation modules.
  opentelemetry: {
    enabled: true,
  },

  instrumentation: {
    // Disable native HTTP instrumentation — OTel handles it.
    http: {
      enabled: false,
    },
    // Disable legacy Next.js instrumentation — replaced by OTel spans.
    next: {
      enabled: false,
    },
    // Disable undici instrumentation to avoid duplicate client spans.
    // Next.js wraps fetch and creates its own client spans.
    undici: {
      enabled: false,
    },
  },

  logging: {
    level: process.env.NEW_RELIC_LOG || "info",
    // Log to stdout in Docker (instead of a file) for proper container log collection.
    filepath: "stdout",
  },

  distributed_tracing: {
    enabled: process.env.NEW_RELIC_DISTRIBUTED_TRACING_ENABLED !== "false",
  },

  allow_all_headers: true,
  attributes: {
    exclude: [
      // Exclude sensitive headers
      "request.headers.cookie",
      "request.headers.authorization",
      "request.headers.proxyAuthorization",
      "request.headers.setCookie*",
      "request.headers.x*",
      "response.headers.cookie",
      "response.headers.setCookie*",
    ],
  },
};
