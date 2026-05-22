import axios from "axios";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api",
  headers: {
    "Content-Type": "application/json",
  },
});

export interface BookUploadResponse {
  id: string;
  filename: string;
  title: string | null;
  language: string;
  total_pages: number | null;
  status: string;
  created_at: string | null;
}

export interface BookDetail extends BookUploadResponse {
  updated_at: string | null;
}

export interface PageSelectionRequest {
  selected_pages: number[];
}

export interface PageSelectionResponse {
  book_id: string;
  selected_count: number;
  status: string;
}

export interface PageResponse {
  id: string;
  page_number: number;
  image_path: string | null;
  preprocessing_config: Record<string, unknown> | null;
}

export const uploadBook = async (
  file: File,
  title?: string,
  language: string = "tel"
): Promise<BookUploadResponse> => {
  const formData = new FormData();
  formData.append("file", file);
  if (title) {
    formData.append("title", title);
  }
  formData.append("language", language);

  const response = await api.post<BookUploadResponse>("/books/upload", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });

  return response.data;
};

export const getBook = async (bookId: string): Promise<BookDetail> => {
  const response = await api.get<BookDetail>(`/books/${bookId}`);
  return response.data;
};

export const getThumbnailUrl = (bookId: string, pageNumber: number): string => {
  return `${api.defaults.baseURL}/books/${bookId}/pages/${pageNumber}/thumbnail`;
};

export const selectPages = async (
  bookId: string,
  selectedPages: number[]
): Promise<PageSelectionResponse> => {
  const response = await api.post<PageSelectionResponse>(
    `/books/${bookId}/pages`,
    {
      selected_pages: selectedPages,
    }
  );
  return response.data;
};

export const getBookPages = async (bookId: string): Promise<PageResponse[]> => {
  const response = await api.get<PageResponse[]>(`/books/${bookId}/pages`);
  return response.data;
};