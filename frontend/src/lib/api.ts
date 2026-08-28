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

  const params = new URLSearchParams({ language });

  const response = await api.post<BookUploadResponse>(
    `/books/upload?${params.toString()}`,
    formData,
    {
      headers: {
        "Content-Type": undefined,
      },
    }
  );

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

export interface ModelInfo {
  name: string;
  size_gb: number | null;
  parameter_count: string | null;
}

export interface ExtractionRequest {
  model: string;
  temperature: number;
  max_tokens: number;
  fields_per_batch: number;
  custom_system_prompt?: string | null;
  custom_extraction_prompt?: string | null;
}

export interface ExtractionResponse {
  job_id: string;
  book_id: string;
  status: string;
  total_batches: number;
}

export interface MetadataFieldDefinition {
  field_name: string;
  display_name: string;
  wikidata_property: string | null;
  batch_group: string;
}

export interface MetadataResponse {
  book_id: string;
  fields: Record<string, string>;
  updated_at: string | null;
}

export interface MetadataUpdateRequest {
  fields: Record<string, string>;
}

export interface LlmRunResponse {
  id: string;
  job_id: string;
  model: string;
  prompt_template: string | null;
  batch_config: Record<string, unknown> | null;
  raw_response: string | null;
  parsed_fields: Record<string, string> | null;
  created_at: string | null;
}

export const DEFAULT_EXTRACTION_CONFIG: ExtractionRequest = {
  model: "airavata",
  temperature: 0.3,
  max_tokens: 2048,
  fields_per_batch: 10,
};

export const getAvailableModels = async (): Promise<ModelInfo[]> => {
  const response = await api.get<ModelInfo[]>("/books/models");
  return response.data;
};

export const runExtraction = async (
  bookId: string,
  config: ExtractionRequest
): Promise<ExtractionResponse> => {
  const response = await api.post<ExtractionResponse>(
    `/books/${bookId}/run-extraction`,
    config
  );
  return response.data;
};

export const retryExtraction = async (
  bookId: string,
  config: ExtractionRequest
): Promise<ExtractionResponse> => {
  const response = await api.post<ExtractionResponse>(
    `/books/${bookId}/retry-extraction`,
    config
  );
  return response.data;
};

export const getMetadata = async (bookId: string): Promise<MetadataResponse> => {
  const response = await api.get<MetadataResponse>(`/books/${bookId}/metadata`);
  return response.data;
};

export const updateMetadata = async (
  bookId: string,
  fields: Record<string, string>
): Promise<MetadataResponse> => {
  const response = await api.put<MetadataResponse>(`/books/${bookId}/metadata`, {
    fields,
  });
  return response.data;
};

export const getMetadataFieldDefinitions = async (
  bookId: string
): Promise<MetadataFieldDefinition[]> => {
  const response = await api.get<MetadataFieldDefinition[]>(
    `/books/${bookId}/metadata/fields`
  );
  return response.data;
};

export interface FieldEvidence {
  field_name: string;
  value: string | null;
  confidence: number | null;
  extraction_method: string;
  source_page_number: number | null;
  source_text_snippet: string | null;
}

export const getMetadataEvidence = async (
  bookId: string
): Promise<FieldEvidence[]> => {
  const response = await api.get<FieldEvidence[]>(
    `/books/${bookId}/metadata/evidence`
  );
  return response.data;
};

export const getLlmRuns = async (bookId: string): Promise<LlmRunResponse[]> => {
  const response = await api.get<LlmRunResponse[]>(`/books/${bookId}/llm-runs`);
  return response.data;
};

export interface BookSearchResult {
  id: string;
  title: string | null;
  filename: string;
  language: string;
  status: string;
  total_pages: number | null;
  created_at: string | null;
  metadata_fields: Record<string, string> | null;
  thumbnail_url: string | null;
}

export interface BookListResponse {
  items: BookSearchResult[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface BookDetailPage {
  id: string;
  page_number: number;
  image_url: string;
  ocr_text: string | null;
  ocr_confidence: number | null;
}

export interface BookDetailResponse {
  book: BookDetail;
  metadata: Record<string, string> | null;
  metadata_updated_at: string | null;
  pages: BookDetailPage[];
  llm_runs: LlmRunResponse[];
  jobs: JobResponse[];
}

export interface FilterOptions {
  languages: string[];
  statuses: string[];
  genres: string[];
  publishers: string[];
}

export interface LibrarySearchParams {
  query?: string;
  language?: string;
  status?: string;
  genre?: string;
  publisher?: string;
  page?: number;
  page_size?: number;
}

export const getLibraryBooks = async (
  params?: LibrarySearchParams
): Promise<BookListResponse> => {
  const searchParams = new URLSearchParams();
  if (params?.query) searchParams.set("query", params.query);
  if (params?.language) searchParams.set("language", params.language);
  if (params?.status) searchParams.set("status", params.status);
  if (params?.genre) searchParams.set("genre", params.genre);
  if (params?.publisher) searchParams.set("publisher", params.publisher);
  if (params?.page) searchParams.set("page", String(params.page));
  if (params?.page_size) searchParams.set("page_size", String(params.page_size));

  const qs = searchParams.toString();
  const url = `/library/books${qs ? `?${qs}` : ""}`;
  const response = await api.get<BookListResponse>(url);
  return response.data;
};

export const searchLibrary = async (
  q: string,
  language?: string,
  limit: number = 20
): Promise<BookSearchResult[]> => {
  const params = new URLSearchParams({ q, limit: String(limit) });
  if (language) params.set("language", language);
  const response = await api.get<BookSearchResult[]>(
    `/library/search?${params.toString()}`
  );
  return response.data;
};

export const getBookDetail = async (
  bookId: string
): Promise<BookDetailResponse> => {
  const response = await api.get<BookDetailResponse>(
    `/library/books/${bookId}/detail`
  );
  return response.data;
};

export const getFilterOptions = async (): Promise<FilterOptions> => {
  const response = await api.get<FilterOptions>("/library/filters");
  return response.data;
};

// ─────────────────────────────────────────────────────────────────────────────
// Bulk Operations
// ─────────────────────────────────────────────────────────────────────────────

export interface BulkStatsResponse {
  total_books: number;
  books_with_metadata: number;
  languages: Record<string, number>;
  statuses: Record<string, number>;
}

export interface BulkExportParams {
  language?: string;
  status?: string;
}

export interface BulkImportResult {
  total_rows: number;
  books_updated: number;
  books_not_found: number;
  fields_changed: number;
  errors: string[];
}

export const getBulkStats = async (): Promise<BulkStatsResponse> => {
  const response = await api.get<BulkStatsResponse>("/bulk/stats");
  return response.data;
};

export const bulkExport = async (params?: BulkExportParams): Promise<Blob> => {
  const searchParams = new URLSearchParams();
  if (params?.language) searchParams.set("language", params.language);
  if (params?.status) searchParams.set("status", params.status);

  const qs = searchParams.toString();
  const response = await api.post(`/bulk/export${qs ? `?${qs}` : ""}`, null, {
    responseType: "blob",
  });
  return response.data;
};

export const bulkImport = async (
  file: File,
  mode: string = "merge"
): Promise<BulkImportResult> => {
  const formData = new FormData();
  formData.append("file", file);

  const response = await api.post<BulkImportResult>(
    `/bulk/import?mode=${mode}`,
    formData,
    {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    }
  );
  return response.data;
};

export const bulkExportWikibase = async (params?: {
  language?: string;
}): Promise<Blob> => {
  const searchParams = new URLSearchParams();
  if (params?.language) searchParams.set("language", params.language);

  const qs = searchParams.toString();
  const response = await api.post(
    `/bulk/export-wikibase${qs ? `?${qs}` : ""}`,
    null,
    {
      responseType: "blob",
    }
  );
  return response.data;
};
