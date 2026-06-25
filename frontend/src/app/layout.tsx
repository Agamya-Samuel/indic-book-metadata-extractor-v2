import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Script from "next/script";
import "./globals.css";
import { Providers } from "./providers";
import AppNavbar from "@/components/shared/app-navbar";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Indic Book Metadata Extractor",
  description:
    "OCR-powered metadata extraction from Indic language books",
};

/**
 * Get the New Relic browser monitoring snippet.
 *
 * Tries server-side injection via the Node.js APM agent first. If that
 * returns a placeholder comment (agent not ready), falls back to a static
 * snippet built from NEXT_PUBLIC_* env vars.
 */
function getNewRelicBrowserScript(): string | null {
  if (process.env.NEW_RELIC_ENABLED !== "true") {
    return null;
  }

  // Try server-side injection from the APM agent.
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const newrelic = require("newrelic");
    const header = newrelic.getBrowserTimingHeader({
      hasToRemoveScriptWrapper: true,
      allowTransactionlessInjection: true,
    });
    // If the agent returned a real script (not a placeholder comment), use it.
    if (header && !header.startsWith("<!-- NREUM:")) {
      return header;
    }
  } catch {
    // Agent not loaded — fall through to static snippet.
  }

  // Fallback: build the snippet from NEXT_PUBLIC_* env vars.
  const licenseKey = process.env.NEXT_PUBLIC_NEW_RELIC_LICENSE_KEY;
  const appId = process.env.NEXT_PUBLIC_NEW_RELIC_APP_ID;
  const accountId = process.env.NEXT_PUBLIC_NEW_RELIC_ACCOUNT_ID;

  if (!licenseKey || !appId || !accountId) {
    return null;
  }

  return `;window.NREUM||(NREUM={});NREUM.init={distributed_tracing:{enabled:true},privacy:{cookies_enabled:true}};
;NREUM.loader_config={accountID:"${accountId}",trustKey:"${accountId}",agentID:"${appId}",licenseKey:"${licenseKey}",applicationID:"${appId}"};
;NREUM.info={beacon:"bam.nr-data.net",errorBeacon:"bam.nr-data.net",licenseKey:"${licenseKey}",applicationID:"${appId}",sa:1};`;
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const browserScript = getNewRelicBrowserScript();

  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <head>
        {browserScript && (
          <Script
            id="nr-browser-agent"
            strategy="beforeInteractive"
            dangerouslySetInnerHTML={{ __html: browserScript }}
          />
        )}
      </head>
      <body className="min-h-full flex flex-col">
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:px-4 focus:py-2 focus:bg-blue-600 focus:text-white focus:rounded focus:shadow-lg"
        >
          Skip to main content
        </a>
        <Providers>
          <div id="main-content" className="flex-1 flex flex-col">
            <AppNavbar />
            {children}
          </div>
        </Providers>
      </body>
    </html>
  );
}
