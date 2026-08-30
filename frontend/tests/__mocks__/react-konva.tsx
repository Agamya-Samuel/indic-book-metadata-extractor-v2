import { vi } from "vitest";
import React from "react";

export const Stage = vi.fn((props: Record<string, unknown>) => {
  const { children, width, height, onWheel, ...rest } = props;
  return React.createElement(
    "div",
    {
      "data-testid": "konva-stage",
      "data-width": String(width),
      "data-height": String(height),
    },
    children as React.ReactNode
  );
});

export const Layer = vi.fn((props: Record<string, unknown>) => {
  const { children } = props;
  return React.createElement(
    "div",
    { "data-testid": "konva-layer" },
    children as React.ReactNode
  );
});

export const Image = vi.fn((props: Record<string, unknown>) => {
  return React.createElement("div", { "data-testid": "konva-image" });
});

export const Rect = vi.fn((props: Record<string, unknown>) => {
  const { onClick, ...rest } = props;
  return React.createElement("div", {
    "data-testid": "konva-rect",
    onClick: onClick as React.MouseEventHandler,
  });
});

export const Group = vi.fn((props: Record<string, unknown>) => {
  const { children } = props;
  return React.createElement(
    "div",
    { "data-testid": "konva-group" },
    children as React.ReactNode
  );
});
