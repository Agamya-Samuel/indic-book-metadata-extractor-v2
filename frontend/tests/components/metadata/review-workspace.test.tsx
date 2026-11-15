import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ReviewWorkspace from "@/components/metadata/review-workspace";

function renderWorkspace(sheetOpen = false) {
  const onSheetOpenChange = vi.fn();
  const utils = render(
    <ReviewWorkspace
      sheetOpen={sheetOpen}
      onSheetOpenChange={onSheetOpenChange}
      renderPane={(controls) => (
        <div>
          <span>pane {controls.variant}</span>
          <button
            type="button"
            onClick={controls.onCollapse}
          >{`collapse pane ${controls.variant}`}</button>
          <button
            type="button"
            onClick={controls.onRequestCloseSheet}
          >{`insert done ${controls.variant}`}</button>
        </div>
      )}
    >
      <div>form body</div>
    </ReviewWorkspace>,
  );
  return { ...utils, onSheetOpenChange };
}

beforeEach(() => {
  window.localStorage.clear();
});

describe("ReviewWorkspace", () => {
  it("renders the form and split pane with the default width", () => {
    renderWorkspace();

    expect(screen.getByText("form body")).toBeDefined();
    expect(screen.getByText("pane split")).toBeDefined();
    const separator = screen.getByRole("separator");
    expect(separator.getAttribute("aria-valuenow")).toBe("420");
    expect(separator.getAttribute("aria-orientation")).toBe("vertical");
  });

  it("resizes the pane with the keyboard", () => {
    renderWorkspace();
    const separator = screen.getByRole("separator");

    fireEvent.keyDown(separator, { key: "ArrowRight" });
    expect(separator.getAttribute("aria-valuenow")).toBe("404");

    fireEvent.keyDown(separator, { key: "ArrowRight", shiftKey: true });
    expect(separator.getAttribute("aria-valuenow")).toBe("340");

    fireEvent.keyDown(separator, { key: "Home" });
    expect(separator.getAttribute("aria-valuenow")).toBe("320");

    fireEvent.keyDown(separator, { key: "End" });
    expect(separator.getAttribute("aria-valuenow")).toBe("640");
  });

  it("persists the width across remounts", () => {
    const first = renderWorkspace();
    fireEvent.keyDown(screen.getByRole("separator"), { key: "ArrowRight" });
    expect(window.localStorage.getItem("metadata-review:pane-width")).toBe(
      "404",
    );
    first.unmount();

    renderWorkspace();
    expect(
      screen.getByRole("separator").getAttribute("aria-valuenow"),
    ).toBe("404");
  });

  it("collapses and expands the desktop pane", () => {
    renderWorkspace();

    fireEvent.click(screen.getByRole("button", { name: "collapse pane split" }));
    expect(screen.queryByRole("separator")).toBeNull();
    expect(screen.getByText("pane sheet")).toBeDefined();
    expect(
      window.localStorage.getItem("metadata-review:pane-collapsed"),
    ).toBe("true");

    fireEvent.click(screen.getByRole("button", { name: "Expand OCR reference" }));
    expect(screen.getByRole("separator")).toBeDefined();
  });

  it("collapses the pane with Enter on the separator", () => {
    renderWorkspace();
    fireEvent.keyDown(screen.getByRole("separator"), { key: "Enter" });
    expect(screen.queryByRole("separator")).toBeNull();
  });

  it("opens the sheet and reports a close request", () => {
    const { onSheetOpenChange, rerender } = renderWorkspace(false);
    const dialog = document.querySelector("dialog");
    expect(dialog?.hasAttribute("open")).toBe(false);

    rerender(
      <ReviewWorkspace
        sheetOpen
        onSheetOpenChange={onSheetOpenChange}
        renderPane={(controls) => (
          <div>
            <span>pane {controls.variant}</span>
            <button
              type="button"
              onClick={controls.onRequestCloseSheet}
            >{`insert done ${controls.variant}`}</button>
          </div>
        )}
      >
        <div>form body</div>
      </ReviewWorkspace>,
    );

    expect(dialog?.hasAttribute("open")).toBe(true);

    fireEvent.click(screen.getByRole("button", { name: "insert done sheet" }));
    expect(onSheetOpenChange).toHaveBeenCalledWith(false);
  });
});
