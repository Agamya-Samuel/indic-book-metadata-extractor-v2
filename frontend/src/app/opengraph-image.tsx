import { ImageResponse } from "next/og";
import { SITE_DESCRIPTION, SITE_NAME } from "@/lib/site";

export const alt = `${SITE_NAME} — OCR and metadata extraction for Indic books`;
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const CHIPS = ["Tesseract OCR", "Local LLM", "Wikibase export"];

export default function OpenGraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: "#f6f7f9",
          padding: "64px 72px",
          position: "relative",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
          <div
            style={{
              width: 46,
              height: 46,
              borderRadius: 11,
              background: "#204569",
              color: "#ffffff",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 17,
              fontWeight: 700,
              letterSpacing: 1,
            }}
          >
            OKI
          </div>
          <div
            style={{
              fontSize: 19,
              letterSpacing: 3.5,
              color: "#5a6473",
            }}
          >
            OPEN KNOWLEDGE INITIATIVES · IIIT HYDERABAD
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", maxWidth: 760 }}>
          <div
            style={{
              fontSize: 74,
              fontWeight: 700,
              letterSpacing: -2,
              lineHeight: 1.05,
              color: "#0d1c2a",
            }}
          >
            {SITE_NAME}
          </div>
          <div
            style={{
              marginTop: 26,
              fontSize: 29,
              lineHeight: 1.4,
              color: "#3f4a5a",
            }}
          >
            {SITE_DESCRIPTION}
          </div>
        </div>

        <div style={{ display: "flex", gap: 12 }}>
          {CHIPS.map((chip) => (
            <div
              key={chip}
              style={{
                display: "flex",
                alignItems: "center",
                padding: "10px 18px",
                borderRadius: 999,
                border: "1px solid #cfd7e2",
                background: "#ffffff",
                color: "#204569",
                fontSize: 20,
                fontWeight: 500,
              }}
            >
              {chip}
            </div>
          ))}
        </div>

        <div
          style={{
            position: "absolute",
            right: 72,
            top: 168,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <div
            style={{
              position: "absolute",
              width: 190,
              height: 250,
              borderRadius: 18,
              background: "#dfe6ee",
              marginLeft: -150,
              marginTop: -14,
            }}
          />
          <div
            style={{
              position: "absolute",
              width: 190,
              height: 250,
              borderRadius: 18,
              background: "#c3d1e0",
              marginLeft: -75,
            }}
          />
          <div
            style={{
              width: 190,
              height: 250,
              borderRadius: 18,
              background: "#204569",
              color: "#ffffff",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 54,
              fontWeight: 700,
              letterSpacing: 2,
            }}
          >
            IB
          </div>
        </div>
      </div>
    ),
    size,
  );
}
