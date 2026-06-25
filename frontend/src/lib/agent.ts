/**
 * New Relic Agent Loader
 *
 * Loads the New Relic Node.js agent and waits for it to connect to the
 * collector before returning. This ensures getBrowserTimingHeader() has
 * the data it needs to generate the browser monitoring snippet.
 *
 * Only loaded on the server (Node.js runtime) — never bundled for the client.
 */

import type { EventEmitter } from "node:events";

export async function loadNewRelicAgent() {
  const { default: newrelic } = await import("newrelic");

  const agent = newrelic?.agent as
    | (EventEmitter & { collector?: { isConnected?: () => boolean } })
    | undefined;

  if (!agent || agent.collector?.isConnected?.()) {
    return newrelic;
  }

  // Wait up to 8 seconds for the agent to connect to New Relic's collector.
  await new Promise<void>((resolve) => {
    const done = () => {
      clearTimeout(timer);
      agent.removeListener("started", done);
      agent.removeListener("errored", done);
      resolve();
    };

    const timer = setTimeout(done, 8000);

    agent.once("started", done);
    agent.once("errored", done);
  });

  return newrelic;
}
