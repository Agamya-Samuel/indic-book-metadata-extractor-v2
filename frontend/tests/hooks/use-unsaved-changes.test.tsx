import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { useUnsavedChanges } from "@/hooks/use-unsaved-changes";

describe("useUnsavedChanges", () => {
  let confirmSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
  });

  afterEach(() => {
    confirmSpy.mockRestore();
    document.body.innerHTML = "";
  });

  it("registers a beforeunload guard only while active", () => {
    const { rerender, unmount } = renderHook(
      ({ active }) => useUnsavedChanges(active),
      { initialProps: { active: true } },
    );

    const event = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(true);

    rerender({ active: false });
    const second = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(second);
    expect(second.defaultPrevented).toBe(false);

    unmount();
  });

  it("blocks in-app link navigation when the user declines", () => {
    renderHook(() => useUnsavedChanges(true));

    const link = document.createElement("a");
    link.href = "/somewhere";
    link.textContent = "Go";
    document.body.appendChild(link);

    const event = new MouseEvent("click", { bubbles: true, cancelable: true, button: 0 });
    link.dispatchEvent(event);

    expect(confirmSpy).toHaveBeenCalled();
    expect(event.defaultPrevented).toBe(true);
  });

  it("allows in-app navigation when the user confirms", () => {
    confirmSpy.mockReturnValue(true);
    renderHook(() => useUnsavedChanges(true));

    const link = document.createElement("a");
    link.href = "/somewhere";
    document.body.appendChild(link);

    const event = new MouseEvent("click", { bubbles: true, cancelable: true, button: 0 });
    link.dispatchEvent(event);

    expect(event.defaultPrevented).toBe(false);
  });
});