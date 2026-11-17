import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono, Noto_Serif } from "next/font/google";
import Script from "next/script";
import "./globals.css";
import { Providers } from "./providers";
import AppNavbar from "@/components/shared/app-navbar";
import { RouteGuard } from "@/components/auth/route-guard";
import MaintenanceGate from "@/components/auth/maintenance-gate";
import { themeInitScript } from "@/components/shared/theme-provider";
import {
  SITE_DESCRIPTION,
  SITE_KEYWORDS,
  SITE_LOCALE,
  SITE_NAME,
  SITE_SHORT_NAME,
  SITE_URL,
} from "@/lib/site";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

// Display face for the scholarly register. Noto Serif (Latin) carries
// the English display voice; the system font stack below already has
// "Noto Serif Telugu / Devanagari / Tamil / Bengali" as fallbacks, so
// any Indic-script text picks up the matching Noto Serif variant from
// the OS without us shipping a second font.
const notoSerif = Noto_Serif({
  variable: "--font-noto-serif",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  style: ["normal", "italic"],
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: SITE_URL,
  title: {
    default: SITE_NAME,
    template: "%s · Indic Books",
  },
  description: SITE_DESCRIPTION,
  applicationName: SITE_NAME,
  authors: [
    { name: "Open Knowledge Initiatives (OKI), IIIT Hyderabad" },
  ],
  creator: "Open Knowledge Initiatives (OKI), IIIT Hyderabad",
  publisher: "Open Knowledge Initiatives (OKI), IIIT Hyderabad",
  keywords: SITE_KEYWORDS,
  category: "digital humanities",
  openGraph: {
    type: "website",
    locale: SITE_LOCALE,
    siteName: SITE_NAME,
    title: SITE_NAME,
    description: SITE_DESCRIPTION,
  },
  twitter: {
    card: "summary_large_image",
    title: SITE_NAME,
    description: SITE_DESCRIPTION,
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-image-preview": "large",
      "max-snippet": -1,
      "max-video-preview": -1,
    },
  },
  formatDetection: { email: false, address: false, telephone: false },
  appleWebApp: {
    capable: true,
    title: SITE_SHORT_NAME,
    statusBarStyle: "default",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  colorScheme: "light dark",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#0d1c2a" },
  ],
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
      className={`${geistSans.variable} ${geistMono.variable} ${notoSerif.variable} h-full antialiased`}
    >
      <head>
        <Script
          id="theme-init"
          strategy="beforeInteractive"
          dangerouslySetInnerHTML={{ __html: themeInitScript }}
        />
        {browserScript && (
          <Script
            id="nr-browser-agent"
            strategy="beforeInteractive"
            dangerouslySetInnerHTML={{ __html: browserScript }}
          />
        )}
      </head>
      <body className="flex min-h-dvh flex-col">
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:px-4 focus:py-2 focus:bg-[var(--accent)] focus:text-[var(--text-inverse)] focus:rounded-[var(--radius)] focus:shadow-[var(--shadow)]"
        >
          Skip to main content
        </a>
        <Providers>
          <MaintenanceGate>
            <div
              id="main-content"
              tabIndex={-1}
              className="flex min-h-0 flex-1 flex-col focus:outline-none"
            >
              <AppNavbar />
              <RouteGuard>{children}</RouteGuard>
            </div>
          </MaintenanceGate>
        </Providers>
      </body>
    </html>
  );
}
