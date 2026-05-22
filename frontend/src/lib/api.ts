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
  preprocessing_config: PreprocessingConfig | null;
}

export interface PreprocessingConfig {
  grayscale: boolean;
  brightness: number;
  contrast: number;
  binarization: "otsu" | "adaptive" | null;
  adaptive_block_size: number;
  adaptive_c: number;
  deskew: boolean;
  denoise: boolean;
  denoise_strength: number;
}

export interface PreprocessingResponse {
  page_id: string;
  processed_image_url: string;
  config_applied: PreprocessingConfig;
}

export interface OcrWord {
  text: string;
  confidence: number;
  bbox: { x: number; y: number; w: number; h: number };
  block_num: number;
  line_num: number;
  word_num: number;
}

export interface OcrResultResponse {
  page_id: string;
  raw_text: string | null;
  bounding_boxes: OcrWord[] | null;
  confidence: number | null;
  language_detected: string | null;
  corrected_text: string | null;
}

export interface JobResponse {
  id: string;
  book_id: string | null;
  job_type: string;
  status: string;
  progress: number;
  created_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  error_log: string | null;
}

export interface OcrPageStatus {
  page_number: number;
  page_id: string;
  has_ocr: boolean;
  confidence: number | null;
}

export interface OcrStatusResponse {
  total_pages: number;
  ocr_complete_count: number;
  ocr_pending_count: number;
  avg_confidence: number | null;
  pages: OcrPageStatus[];
}

export const DEFAULT_PREPROCESSING_CONFIG: PreprocessingConfig = {
  grayscale: true,
  brightness: 0,
  contrast: 0,
  binarization: null,
  adaptive_block_size: 11,
  adaptive_c: 2,
  deskew: true,
  denoise: false,
  denoise_strength: 10,
};

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

export const updatePreprocessing = async (
  pageId: string,
  config: PreprocessingConfig
): Promise<PreprocessingResponse> => {
  const response = await api.put<PreprocessingResponse>(
    `/pages/${pageId}/preprocessing`,
    config
  );
  return response.data;
};

export const getPageImageUrl = (pageId: string): string => {
  return `${api.defaults.baseURL}/pages/${pageId}/image`;
};

export const getOcrResult = async (pageId: string): Promise<OcrResultResponse> => {
  const response = await api.get<OcrResultResponse>(`/pages/${pageId}/ocr`);
  return response.data;
};

export const updateOcrCorrection = async (
  pageId: string,
  correctedText: string
): Promise<OcrResultResponse> => {
  const response = await api.put<OcrResultResponse>(`/pages/${pageId}/ocr`, {
    corrected_text: correctedText,
  });
  return response.data;
};

export const runOcr = async (bookId: string): Promise<JobResponse> => {
  const response = await api.post<JobResponse>(`/books/${bookId}/run-ocr`);
  return response.data;
};

export const getBookJobs = async (bookId: string): Promise<JobResponse[]> => {
  const response = await api.get<JobResponse[]>(`/books/${bookId}/jobs`);
  return response.data;
};

export const getOcrStatus = async (bookId: string): Promise<OcrStatusResponse> => {
  const response = await api.get<OcrStatusResponse>(`/books/${bookId}/ocr-status`);
  return response.data;
};

export const getJob = async (bookId: string, jobId: string): Promise<JobResponse | undefined> => {
  const jobs = await getBookJobs(bookId);
  return jobs.find((j) => j.id === jobId);
};
