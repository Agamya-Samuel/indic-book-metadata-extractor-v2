/**
 * New Relic Browser Agent (Real User Monitoring)
 *
 * Replace the placeholder values below with the values from your
 * New Relic Browser application configuration:
 *   1. Go to "Add more data" > "Browser" > "Copy/paste JavaScript code"
 *   2. Copy the `info`, `loader_config`, and `init` objects
 *
 * The values are read from NEXT_PUBLIC_ env vars so they can be
 * baked into the client bundle at build time.
 */

import { BrowserAgent } from "@newrelic/browser-agent/loaders/browser-agent";

const licenseKey = process.env.NEXT_PUBLIC_NEW_RELIC_LICENSE_KEY || "";
const applicationID = process.env.NEXT_PUBLIC_NEW_RELIC_APP_ID || "";
const accountID = process.env.NEXT_PUBLIC_NEW_RELIC_ACCOUNT_ID || "";

// Only initialise when all required keys are present (avoids errors in dev
// environments where New Relic isn't configured).
let browserAgent: BrowserAgent | undefined;

if (licenseKey && applicationID && accountID) {
  browserAgent = new BrowserAgent({
    init: {
      privacy: { cookies_enabled: true },
      page_view_timing: { enabled: true },
      session_trace: { enabled: true },
      ajax: { deny_list: [] },
    },
    info: {
      beacon: "bam.nr-data.net",
      errorBeacon: "bam.nr-data.net",
      licenseKey,
      applicationID,
      sa: 1,
    },
    loader_config: {
      accountID,
      trustKey: accountID,
      agentID: applicationID,
      licenseKey,
      applicationID,
    },
  });
}

export { browserAgent };
