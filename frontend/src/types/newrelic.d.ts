/**
 * Type declaration for the `newrelic` Node.js agent.
 *
 * The official package does not ship TypeScript types.
 * This covers only the APIs we use (getBrowserTimingHeader).
 */

declare module "newrelic" {
  interface BrowserTimingHeaderOptions {
    hasToRemoveScriptWrapper?: boolean;
    allowTransactionlessInjection?: boolean;
  }

  interface NewRelicAgent {
    agent: unknown;
    getBrowserTimingHeader(
      options?: BrowserTimingHeaderOptions,
    ): string;
  }

  const newrelic: NewRelicAgent;
  export default newrelic;
}
