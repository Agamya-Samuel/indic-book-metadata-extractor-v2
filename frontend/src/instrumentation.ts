/**
 * Next.js Instrumentation Hook
 *
 * Loads the New Relic Node.js agent on the server side when the
 * NEXT_RUNTIME is "nodejs" (not "edge"). The agent provides:
 * - Server-side APM (transactions, traces, errors)
 * - Browser monitoring snippet injection via getBrowserTimingHeader()
 * - Distributed tracing across frontend → backend → Celery
 *
 * This file is automatically discovered by Next.js 15+ (no config needed).
 * See: https://nextjs.org/docs/app/building-your-application/optimizing/instrumentation
 */

export async function register() {
  // Only load in the Node.js runtime, not Edge.
  if (process.env.NEXT_RUNTIME !== "nodejs") {
    return;
  }

  // Respect the master toggle from .env
  if (process.env.NEW_RELIC_ENABLED !== "true") {
    return;
  }

  await import("./lib/agent").then(({ loadNewRelicAgent }) =>
    loadNewRelicAgent(),
  );
}
