import { describe, it, expect, beforeEach } from "vitest";
import { useBookStore } from "@/stores/book-store";

describe("useBookStore", () => {
  beforeEach(() => {
    useBookStore.getState().reset();
  });

  it("has correct initial state", () => {
    const state = useBookStore.getState();
    expect(state.currentBookId).toBeNull();
    expect(state.selectedPages).toEqual(new Set());
    expect(state.language).toBe("tel");
  });

  it("sets current book ID", () => {
    useBookStore.getState().setCurrentBookId("book-123");
    expect(useBookStore.getState().currentBookId).toBe("book-123");
  });

  it("toggles page selection on", () => {
    useBookStore.getState().togglePageSelection(5);
    expect(useBookStore.getState().selectedPages.has(5)).toBe(true);
  });

  it("toggles page selection off", () => {
    useBookStore.getState().togglePageSelection(5);
    useBookStore.getState().togglePageSelection(5);
    expect(useBookStore.getState().selectedPages.has(5)).toBe(false);
  });

  it("selects multiple pages", () => {
    useBookStore.getState().selectPages([1, 3, 5]);
    const pages = useBookStore.getState().selectedPages;
    expect(pages.has(1)).toBe(true);
    expect(pages.has(3)).toBe(true);
    expect(pages.has(5)).toBe(true);
    expect(pages.size).toBe(3);
  });

  it("deselects specific pages", () => {
    useBookStore.getState().selectPages([1, 2, 3, 4, 5]);
    useBookStore.getState().deselectPages([2, 4]);
    const pages = useBookStore.getState().selectedPages;
    expect(pages.has(1)).toBe(true);
    expect(pages.has(3)).toBe(true);
    expect(pages.has(5)).toBe(true);
    expect(pages.has(2)).toBe(false);
    expect(pages.has(4)).toBe(false);
  });

  it("clears selection", () => {
    useBookStore.getState().selectPages([1, 2, 3]);
    useBookStore.getState().clearSelection();
    expect(useBookStore.getState().selectedPages.size).toBe(0);
  });

  it("selects all pages", () => {
    useBookStore.getState().selectAllPages(5);
    const pages = useBookStore.getState().selectedPages;
    expect(pages.size).toBe(5);
    expect(pages.has(1)).toBe(true);
    expect(pages.has(5)).toBe(true);
  });

  it("sets language", () => {
    useBookStore.getState().setLanguage("hin");
    expect(useBookStore.getState().language).toBe("hin");
  });

  it("resets to initial state", () => {
    useBookStore.getState().setCurrentBookId("book-1");
    useBookStore.getState().selectPages([1, 2]);
    useBookStore.getState().setLanguage("hin");

    useBookStore.getState().reset();

    const state = useBookStore.getState();
    expect(state.currentBookId).toBeNull();
    expect(state.selectedPages.size).toBe(0);
    expect(state.language).toBe("tel");
  });

  it("selectPages merges with existing selection", () => {
    useBookStore.getState().selectPages([1, 2]);
    useBookStore.getState().selectPages([3, 4]);
    expect(useBookStore.getState().selectedPages.size).toBe(4);
  });
});
