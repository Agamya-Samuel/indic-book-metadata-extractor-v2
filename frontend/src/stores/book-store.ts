import { create } from "zustand";

interface BookStore {
  currentBookId: string | null;
  selectedPages: Set<number>;
  language: string;
  setCurrentBookId: (bookId: string | null) => void;
  togglePageSelection: (pageNumber: number) => void;
  selectPages: (pageNumbers: number[]) => void;
  deselectPages: (pageNumbers: number[]) => void;
  clearSelection: () => void;
  selectAllPages: (totalPages: number) => void;
  setLanguage: (language: string) => void;
  reset: () => void;
}

export const useBookStore = create<BookStore>((set) => ({
  currentBookId: null,
  selectedPages: new Set<number>(),
  language: "tel",

  setCurrentBookId: (bookId) =>
    set({
      currentBookId: bookId,
    }),

  togglePageSelection: (pageNumber) =>
    set((state) => {
      const newSelectedPages = new Set(state.selectedPages);
      if (newSelectedPages.has(pageNumber)) {
        newSelectedPages.delete(pageNumber);
      } else {
        newSelectedPages.add(pageNumber);
      }
      return { selectedPages: newSelectedPages };
    }),

  selectPages: (pageNumbers) =>
    set((state) => {
      const newSelectedPages = new Set(state.selectedPages);
      pageNumbers.forEach((pn) => newSelectedPages.add(pn));
      return { selectedPages: newSelectedPages };
    }),

  deselectPages: (pageNumbers) =>
    set((state) => {
      const newSelectedPages = new Set(state.selectedPages);
      pageNumbers.forEach((pn) => newSelectedPages.delete(pn));
      return { selectedPages: newSelectedPages };
    }),

  clearSelection: () =>
    set({
      selectedPages: new Set<number>(),
    }),

  selectAllPages: (totalPages) =>
    set({
      selectedPages: new Set(Array.from({ length: totalPages }, (_, i) => i + 1)),
    }),

  setLanguage: (language) =>
    set({
      language,
    }),

  reset: () =>
    set({
      currentBookId: null,
      selectedPages: new Set<number>(),
      language: "tel",
    }),
}));