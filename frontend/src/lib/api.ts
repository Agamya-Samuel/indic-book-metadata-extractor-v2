import axios from "axios";

const baseURL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

const api = axios.create({
  baseURL,
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
  },
});

const MUTATION_METHODS = new Set(["post", "put", "patch", "delete"]);

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const prefix = `${name}=`;
  const match = document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(prefix));
  return match ? decodeURIComponent(match.slice(prefix.length)) : null;
}

api.interceptors.request.use((config) => {
  if (config.method && MUTATION_METHODS.has(config.method.toLowerCase())) {
    const csrf = readCookie("csrf_token");
    if (csrf) {
      config.headers = config.headers ?? {};
      config.headers["X-CSRF-Token"] = csrf;
    }
  }
  return config;
});

// Access tokens live for 15 minutes. On the first 401, rotate the refresh
// cookie once and replay the original request. Concurrent requests share a
// single refresh attempt so we never race the rotating token.
let refreshPromise: Promise<boolean> | null = null;

async function refreshSession(): Promise<boolean> {
  try {
    await axios.post(`${baseURL}/auth/refresh`, null, {
      withCredentials: true,
    });
    return true;
  } catch {
    return false;
  }
}

const NO_REFRESH_PATHS = [
  "/auth/login",
  "/auth/register",
  "/auth/refresh",
  "/auth/logout",
  "/auth/forgot-password",
  "/auth/reset-password",
  "/auth/verify-email",
  "/auth/resend-verification",
];

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    const status = error.response?.status;
    const url: string = original?.url ?? "";
    const skip = NO_REFRESH_PATHS.some((path) => url.includes(path));

    if (status === 401 && original && !original._retried && !skip) {
      original._retried = true;
      if (!refreshPromise) {
        refreshPromise = refreshSession().finally(() => {
          refreshPromise = null;
        });
      }
      if (await refreshPromise) {
        return api(original);
      }
    }
    return Promise.reject(error);
  },
);

export type AccountStatus = "pending" | "approved" | "rejected";

export const isApprovedStatus = (
  status: AccountStatus | null | undefined,
): boolean => status === "approved";

export interface AuthUser {
  id: string;
  email: string;
  display_name: string;
  role: "user" | "admin";
  is_active: boolean;
  account_status: AccountStatus;
  rejection_reason: string | null;
  email_verified_at: string | null;
  last_login_at: string | null;
  created_at: string | null;
}

export const getCurrentUser = async (): Promise<AuthUser> => {
  const response = await api.get<AuthUser>("/auth/me");
  return response.data;
};

export const login = async (
  email: string,
  password: string,
): Promise<AuthUser> => {
  const response = await api.post<AuthUser>("/auth/login", { email, password });
  return response.data;
};

export const register = async (payload: {
  email: string;
  display_name: string;
  password: string;
}): Promise<{ message: string; email: string }> => {
  const response = await api.post("/auth/register", payload);
  return response.data;
};

export const logout = async (): Promise<void> => {
  await api.post("/auth/logout");
};

export const verifyEmail = async (token: string): Promise<AuthUser> => {
  const response = await api.post<AuthUser>("/auth/verify-email", { token });
  return response.data;
};

export const resendVerification = async (email: string): Promise<void> => {
  await api.post("/auth/resend-verification", { email });
};

export const requestPasswordReset = async (email: string): Promise<void> => {
  await api.post("/auth/forgot-password", { email });
};

export const resetPassword = async (
  token: string,
  newPassword: string,
): Promise<AuthUser> => {
  const response = await api.post<AuthUser>("/auth/reset-password", {
    token,
    new_password: newPassword,
  });
  return response.data;
};

export const changePassword = async (
  currentPassword: string,
  newPassword: string,
): Promise<void> => {
  await api.post("/auth/change-password", {
    current_password: currentPassword,
    new_password: newPassword,
  });
};

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface PageParams {
  page?: number;
  page_size?: number;
}

const pageQuery = (params?: PageParams): string => {
  const searchParams = new URLSearchParams();
  if (params?.page) searchParams.set("page", String(params.page));
  if (params?.page_size) searchParams.set("page_size", String(params.page_size));
  const qs = searchParams.toString();
  return qs ? `?${qs}` : "";
};

/**
 * Walk a paginated endpoint until every item has been collected.
 * Only for consumers that genuinely need the complete set (counts, filmstrips);
 * user-facing tables should render `Page.items` with `<Pagination>`.
 */
export const fetchAll = async <T>(
  fetchPage: (page: number, size: number) => Promise<Page<T>>,
  size = 100,
): Promise<T[]> => {
  const first = await fetchPage(1, size);
  const items = [...first.items];
  for (let page = 2; page <= first.total_pages; page += 1) {
    const next = await fetchPage(page, size);
    items.push(...next.items);
  }
  return items;
};

export interface BookUploadResponse {
  id: string;
  filename: string;
  title: string | null;
  language: string;
  total_pages: number | null;
  status: string;
  created_at: string | null;
  owner_id?: string | null;
  owner_display_name?: string | null;
}

export interface BookStageResponse {
  id: string;
  book_id: string;
  stage_name: string;
  attempt: number;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  error_log: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface BookDetail extends BookUploadResponse {
  updated_at: string | null;
  needs_review?: boolean;
  low_confidence_count?: number;
  stages?: BookStageResponse[];
  owner_email?: string | null;
  /** Signed token for <img> thumbnail URLs (survives access-token expiry). */
  thumbnail_token?: string | null;
}

export interface PageSelectionRequest {
  selected_pages: number[];
}

export interface PageSelectionResponse {
  book_id: string;
  selected_count: number;
  status: string;
  job_id: string | null;
}

export interface PageResponse {
  id: string;
  page_number: number;
  image_path: string | null;
  preprocessing_config: PreprocessingConfig | null;
  has_processed_image?: boolean;
  image_url?: string | null;
  preview_url?: string | null;
  ocr_error?: string | null;
  ocr_text?: string | null;
  ocr_confidence?: number | null;
}

export interface PreprocessingConfig {
  grayscale: boolean;
  brightness: number;
  contrast: number;
  binarization: "otsu" | "adaptive" | "sauvola" | "none" | null;
  adaptive_block_size: number;
  adaptive_c: number;
  deskew: boolean;
  denoise: boolean;
  denoise_strength: number;
  // Advanced operations (previously unreachable from the API).
  upscale_to_300dpi?: boolean;
  remove_borders?: boolean;
  border_content_ratio?: number;
  sauvola_window?: number;
  sauvola_k?: number;
  auto_preprocess?: boolean;
  // Manual rotation. Coarse first, fine (±15°) after deskew.
  rotation?: number;
  rotation_angle?: number;
}

export interface PreprocessingResponse {
  page_id: string;
  processed_image_url: string;
  config_applied: PreprocessingConfig;
}

export interface PreprocessingPreviewResponse {
  page_id: string;
  preview_url: string;
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
  requested_by_id?: string | null;
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
  ocr_error?: string | null;
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
  denoise_strength: 7,
  upscale_to_300dpi: true,
  remove_borders: true,
  border_content_ratio: 0.85,
  sauvola_window: 25,
  sauvola_k: 0.2,
  auto_preprocess: true,
  rotation: 0,
  rotation_angle: 0,
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

export const getBookStages = async (
  bookId: string,
  params?: PageParams,
): Promise<Page<BookStageResponse>> => {
  const response = await api.get<Page<BookStageResponse>>(
    `/books/${bookId}/stages${pageQuery(params)}`,
  );
  return response.data;
};

export const getBookCurrentStages = async (
  bookId: string,
  params?: PageParams,
): Promise<Page<BookStageResponse>> => {
  const response = await api.get<Page<BookStageResponse>>(
    `/books/${bookId}/stages/current${pageQuery(params)}`,
  );
  return response.data;
};

export const getAllBookCurrentStages = async (
  bookId: string,
): Promise<BookStageResponse[]> =>
  fetchAll((page, page_size) =>
    getBookCurrentStages(bookId, { page, page_size }),
  );

export const getThumbnailUrl = (
  bookId: string,
  pageNumber: number,
  token?: string | null,
): string => {
  const base = `${api.defaults.baseURL}/books/${bookId}/pages/${pageNumber}/thumbnail`;
  return token ? `${base}?token=${encodeURIComponent(token)}` : base;
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

export const getBookPages = async (
  bookId: string,
  params?: PageParams & { include_ocr?: boolean },
): Promise<Page<PageResponse>> => {
  const searchParams = new URLSearchParams();
  if (params?.page) searchParams.set("page", String(params.page));
  if (params?.page_size) searchParams.set("page_size", String(params.page_size));
  if (params?.include_ocr) searchParams.set("include_ocr", "true");
  const qs = searchParams.toString();
  const response = await api.get<Page<PageResponse>>(
    `/books/${bookId}/pages${qs ? `?${qs}` : ""}`,
  );
  return response.data;
};

export const getAllBookPages = async (
  bookId: string,
  opts?: { include_ocr?: boolean },
): Promise<PageResponse[]> =>
  fetchAll((page, page_size) =>
    getBookPages(bookId, { page, page_size, ...opts }),
  );

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

export const previewPreprocessing = async (
  pageId: string,
  config: PreprocessingConfig
): Promise<PreprocessingPreviewResponse> => {
  const response = await api.post<PreprocessingPreviewResponse>(
    `/pages/${pageId}/preprocessing/preview`,
    config
  );
  return response.data;
};

export const getPreprocessingPreviewUrl = (pageId: string): string => {
  return `${api.defaults.baseURL}/pages/${pageId}/preprocessing/preview`;
};

export const applyPreprocessingToAll = async (
  bookId: string,
  config: PreprocessingConfig,
): Promise<JobResponse> => {
  const response = await api.post<JobResponse>(
    `/books/${bookId}/preprocessing`,
    config,
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

export const getBookJobs = async (
  bookId: string,
  params?: PageParams,
): Promise<Page<JobResponse>> => {
  const response = await api.get<Page<JobResponse>>(
    `/books/${bookId}/jobs${pageQuery(params)}`,
  );
  return response.data;
};

export const getAllBookJobs = async (bookId: string): Promise<JobResponse[]> =>
  fetchAll((page, page_size) => getBookJobs(bookId, { page, page_size }));

export const getOcrStatus = async (bookId: string): Promise<OcrStatusResponse> => {
  const response = await api.get<OcrStatusResponse>(`/books/${bookId}/ocr-status`);
  return response.data;
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
  fields: Record<string, string | Record<string, string>>;
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
  model: "phi4-mini",
  temperature: 0.3,
  max_tokens: 512,
  fields_per_batch: 10,
};

export const getAvailableModels = async (
  params?: PageParams,
): Promise<Page<ModelInfo>> => {
  const response = await api.get<Page<ModelInfo>>(
    `/books/models${pageQuery(params)}`,
  );
  return response.data;
};

export const getAllAvailableModels = async (): Promise<ModelInfo[]> =>
  fetchAll((page, page_size) => getAvailableModels({ page, page_size }));

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
  fields: Record<string, string | Record<string, string>>
): Promise<MetadataResponse> => {
  const response = await api.put<MetadataResponse>(`/books/${bookId}/metadata`, {
    fields,
  });
  return response.data;
};

export const getMetadataFieldDefinitions = async (
  bookId: string,
  params?: PageParams,
): Promise<Page<MetadataFieldDefinition>> => {
  const response = await api.get<Page<MetadataFieldDefinition>>(
    `/books/${bookId}/metadata/fields${pageQuery(params)}`,
  );
  return response.data;
};

export const getAllMetadataFieldDefinitions = async (
  bookId: string,
): Promise<MetadataFieldDefinition[]> =>
  fetchAll((page, page_size) =>
    getMetadataFieldDefinitions(bookId, { page, page_size }),
  );

export const completeReview = async (
  bookId: string
): Promise<MetadataResponse> => {
  const response = await api.post<MetadataResponse>(
    `/books/${bookId}/review/complete`
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
  bookId: string,
  params?: PageParams,
): Promise<Page<FieldEvidence>> => {
  const response = await api.get<Page<FieldEvidence>>(
    `/books/${bookId}/metadata/evidence${pageQuery(params)}`,
  );
  return response.data;
};

export const getAllMetadataEvidence = async (
  bookId: string,
): Promise<FieldEvidence[]> =>
  fetchAll((page, page_size) =>
    getMetadataEvidence(bookId, { page, page_size }),
  );

export const getLlmRuns = async (
  bookId: string,
  params?: PageParams,
): Promise<Page<LlmRunResponse>> => {
  const response = await api.get<Page<LlmRunResponse>>(
    `/books/${bookId}/llm-runs${pageQuery(params)}`,
  );
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
  owner_id?: string | null;
  owner_display_name?: string | null;
  owner_email?: string | null;
}

export type BookListResponse = Page<BookSearchResult>;

export interface BookDetailResponse {
  book: BookDetail;
  metadata: Record<string, string> | null;
  metadata_updated_at: string | null;
  owner_display_name?: string | null;
}

export interface FilterOptions {
  languages: string[];
  statuses: string[];
  genres: string[];
  publishers: string[];
}

// The catalog is admin-scoped: `/admin/books` serves both the admin list and
// the book detail view via
// `getAdminBooks`, so the filter set cannot drift between the two views.
export const getBookDetail = async (
  bookId: string
): Promise<BookDetailResponse> => {
  const response = await api.get<BookDetailResponse>(
    `/books/${bookId}/detail`
  );
  return response.data;
};

export const getFilterOptions = async (): Promise<FilterOptions> => {
  const response = await api.get<FilterOptions>("/admin/filters");
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

// ─────────────────────────────────────────────────────────────────────────────
// Admin
// ─────────────────────────────────────────────────────────────────────────────

export interface AdminStatsResponse {
  total_books: number;
  books_with_metadata: number;
  languages: Record<string, number>;
  statuses: Record<string, number>;
  jobs: {
    queued: number;
    running: number;
    failed_recent: number;
    completed_recent: number;
  };
  users?: {
    total: number;
    active: number;
    pending: number;
  };
  pending_user_count?: number;
  disk_usage_mb: number;
}

export interface AdminBooksParams {
  query?: string;
  language?: string;
  status?: string;
  genre?: string;
  publisher?: string;
  has_metadata?: boolean;
  owner_id?: string;
  page?: number;
  page_size?: number;
}

export interface AdminJobRow {
  id: string;
  book_id: string | null;
  requested_by_id?: string | null;
  book_title: string | null;
  book_filename: string;
  owner_display_name?: string | null;
  owner_email?: string | null;
  job_type: "page_extraction" | "ocr" | "llm" | "preprocessing";
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  progress: number;
  created_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  error_log: string | null;
}

export type AdminJobsResponse = Page<AdminJobRow>;

export interface AdminJobsParams {
  status?: string;
  job_type?: "page_extraction" | "ocr" | "llm" | "preprocessing";
  book_id?: string;
  owner_id?: string;
  page?: number;
  page_size?: number;
}

export const getAdminStats = async (): Promise<AdminStatsResponse> => {
  const response = await api.get<AdminStatsResponse>("/admin/stats");
  return response.data;
};

export const getPendingUserCount = async (): Promise<number> => {
  const response = await api.get<{ count: number }>(
    "/admin/users/pending-count",
  );
  return response.data.count;
};

export const getAdminBooks = async (
  params?: AdminBooksParams
): Promise<BookListResponse> => {
  const searchParams = new URLSearchParams();
  if (params?.query) searchParams.set("query", params.query);
  if (params?.language) searchParams.set("language", params.language);
  if (params?.status) searchParams.set("status", params.status);
  if (params?.genre) searchParams.set("genre", params.genre);
  if (params?.publisher) searchParams.set("publisher", params.publisher);
  if (typeof params?.has_metadata === "boolean") {
    searchParams.set("has_metadata", String(params.has_metadata));
  }
  if (params?.owner_id) searchParams.set("owner_id", params.owner_id);
  if (params?.page) searchParams.set("page", String(params.page));
  if (params?.page_size) searchParams.set("page_size", String(params.page_size));

  const qs = searchParams.toString();
  const response = await api.get<BookListResponse>(
    `/admin/books${qs ? `?${qs}` : ""}`
  );
  return response.data;
};

export const deleteAdminBook = async (bookId: string): Promise<void> => {
  await api.delete(`/admin/books/${bookId}`);
};

export const resetAdminBook = async (
  bookId: string
): Promise<{ id: string; status: string }> => {
  const response = await api.post<{ id: string; status: string }>(
    `/admin/books/${bookId}/reset`
  );
  return response.data;
};

export const rerunAdminOcr = async (
  bookId: string
): Promise<{ job_id: string; book_id: string; status: string }> => {
  const response = await api.post<{ job_id: string; book_id: string; status: string }>(
    `/admin/books/${bookId}/rerun-ocr`
  );
  return response.data;
};

export const rerunAdminExtraction = async (
  bookId: string
): Promise<{ job_id: string; book_id: string; status: string }> => {
  const response = await api.post<{ job_id: string; book_id: string; status: string }>(
    `/admin/books/${bookId}/rerun-extraction`
  );
  return response.data;
};

export const getAdminJobs = async (
  params?: AdminJobsParams
): Promise<AdminJobsResponse> => {
  const searchParams = new URLSearchParams();
  if (params?.status) searchParams.set("status", params.status);
  if (params?.job_type) searchParams.set("job_type", params.job_type);
  if (params?.book_id) searchParams.set("book_id", params.book_id);
  if (params?.owner_id) searchParams.set("owner_id", params.owner_id);
  if (params?.page) searchParams.set("page", String(params.page));
  if (params?.page_size) searchParams.set("page_size", String(params.page_size));

  const qs = searchParams.toString();
  const response = await api.get<AdminJobsResponse>(
    `/admin/jobs${qs ? `?${qs}` : ""}`
  );
  return response.data;
};

export const cancelAdminJob = async (
  jobId: string
): Promise<{ id: string; status: string }> => {
  const response = await api.post<{ id: string; status: string }>(
    `/admin/jobs/${jobId}/cancel`
  );
  return response.data;
};

// ─────────────────────────────────────────────────────────────────────────────
// Dashboard (per-user)
// ─────────────────────────────────────────────────────────────────────────────

export interface DashboardSummary {
  books: {
    total: number;
    by_status: Record<string, number>;
  };
  jobs: {
    total: number;
    queued: number;
    running: number;
    completed: number;
    failed: number;
    cancelled: number;
  };
  queue: {
    ocr: number;
    llm: number;
  };
}

export interface DashboardJobRow {
  id: string;
  book_id: string | null;
  book_title: string | null;
  book_filename: string | null;
  job_type: string;
  status: string;
  progress: number;
  queue_ahead: number | null;
  created_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  error_log: string | null;
}

export type DashboardJobsResponse = Page<DashboardJobRow>;

export interface DashboardJobsParams {
  status?: string;
  job_type?: string;
  page?: number;
  page_size?: number;
}

export const getDashboardSummary = async (): Promise<DashboardSummary> => {
  const response = await api.get<DashboardSummary>("/dashboard/summary");
  return response.data;
};

export const getDashboardBooks = async (params?: {
  status?: string;
  page?: number;
  page_size?: number;
}): Promise<BookListResponse> => {
  const searchParams = new URLSearchParams();
  if (params?.status) searchParams.set("status", params.status);
  if (params?.page) searchParams.set("page", String(params.page));
  if (params?.page_size) searchParams.set("page_size", String(params.page_size));
  const qs = searchParams.toString();
  const response = await api.get<BookListResponse>(
    `/dashboard/books${qs ? `?${qs}` : ""}`,
  );
  return response.data;
};

export const getDashboardJobs = async (
  params?: DashboardJobsParams,
): Promise<DashboardJobsResponse> => {
  const searchParams = new URLSearchParams();
  if (params?.status) searchParams.set("status", params.status);
  if (params?.job_type) searchParams.set("job_type", params.job_type);
  if (params?.page) searchParams.set("page", String(params.page));
  if (params?.page_size) searchParams.set("page_size", String(params.page_size));
  const qs = searchParams.toString();
  const response = await api.get<DashboardJobsResponse>(
    `/dashboard/jobs${qs ? `?${qs}` : ""}`,
  );
  return response.data;
};

export const cancelJob = async (
  jobId: string,
): Promise<{ id: string; status: string }> => {
  const response = await api.post<{ id: string; status: string }>(
    `/dashboard/jobs/${jobId}/cancel`,
  );
  return response.data;
};

// Owner-scoped book management (the same helpers are available to admins).

export const deleteBook = async (bookId: string): Promise<void> => {
  await api.delete(`/books/${bookId}`);
};

export const resetBook = async (
  bookId: string,
): Promise<{ id: string; status: string }> => {
  const response = await api.post<{ id: string; status: string }>(
    `/books/${bookId}/reset`,
  );
  return response.data;
};

export const rerunOcr = async (
  bookId: string,
): Promise<{ job_id: string; book_id: string; status: string }> => {
  const response = await api.post<{
    job_id: string;
    book_id: string;
    status: string;
  }>(`/books/${bookId}/rerun-ocr`);
  return response.data;
};

export const rerunExtraction = async (
  bookId: string,
): Promise<{ job_id: string; book_id: string; status: string }> => {
  const response = await api.post<{
    job_id: string;
    book_id: string;
    status: string;
  }>(`/books/${bookId}/rerun-extraction`);
  return response.data;
};

// ─────────────────────────────────────────────────────────────────────────────
// Admin user management
// ─────────────────────────────────────────────────────────────────────────────

export type AdminUser = AuthUser;

export interface AdminUserDetail extends AdminUser {
  book_count: number;
  active_job_count: number;
}

export type AdminUsersResponse = Page<AdminUser>;

export interface AdminUsersParams {
  query?: string;
  role?: "user" | "admin";
  is_active?: boolean;
  account_status?: AccountStatus;
  page?: number;
  page_size?: number;
}

export const getAdminUsers = async (
  params?: AdminUsersParams,
): Promise<AdminUsersResponse> => {
  const searchParams = new URLSearchParams();
  if (params?.query) searchParams.set("query", params.query);
  if (params?.role) searchParams.set("role", params.role);
  if (typeof params?.is_active === "boolean") {
    searchParams.set("is_active", String(params.is_active));
  }
  if (params?.account_status) {
    searchParams.set("account_status", params.account_status);
  }
  if (params?.page) searchParams.set("page", String(params.page));
  if (params?.page_size) searchParams.set("page_size", String(params.page_size));
  const qs = searchParams.toString();
  const response = await api.get<AdminUsersResponse>(
    `/admin/users${qs ? `?${qs}` : ""}`,
  );
  return response.data;
};

export const getAdminUser = async (
  userId: string,
): Promise<AdminUserDetail> => {
  const response = await api.get<AdminUserDetail>(`/admin/users/${userId}`);
  return response.data;
};

export const createAdminUser = async (payload: {
  email: string;
  display_name: string;
  password: string;
  role: "user" | "admin";
}): Promise<AdminUser> => {
  const response = await api.post<AdminUser>("/admin/users", payload);
  return response.data;
};

export const updateAdminUser = async (
  userId: string,
  payload: {
    display_name?: string;
    role?: "user" | "admin";
    is_active?: boolean;
  },
): Promise<AdminUser> => {
  const response = await api.patch<AdminUser>(`/admin/users/${userId}`, payload);
  return response.data;
};

export const approveAdminUser = async (userId: string): Promise<AdminUser> => {
  const response = await api.post<AdminUser>(`/admin/users/${userId}/approve`);
  return response.data;
};

export const rejectAdminUser = async (
  userId: string,
  rejectionReason?: string,
): Promise<AdminUser> => {
  const response = await api.post<AdminUser>(`/admin/users/${userId}/reject`, {
    rejection_reason: rejectionReason || null,
  });
  return response.data;
};

export const resetAdminUserPassword = async (
  userId: string,
  newPassword: string,
): Promise<void> => {
  await api.post(`/admin/users/${userId}/reset-password`, {
    new_password: newPassword,
  });
};

export const deleteAdminUser = async (userId: string): Promise<void> => {
  await api.delete(`/admin/users/${userId}`);
};

// ---------------------------------------------------------------------------
// Notifications
// ---------------------------------------------------------------------------

export interface NotificationRow {
  id: string;
  type:
    | "job_completed"
    | "job_failed"
    | "job_cancelled"
    | "account_approved"
    | "pending_registration";
  title: string;
  body: string;
  link_url: string | null;
  book_id: string | null;
  read_at: string | null;
  created_at: string | null;
}

export type NotificationListResponse = Page<NotificationRow> & {
  unread_count: number;
};

export const getNotifications = async (params?: {
  page?: number;
  page_size?: number;
  unread_only?: boolean;
}): Promise<NotificationListResponse> => {
  const searchParams = new URLSearchParams();
  if (params?.page) searchParams.set("page", String(params.page));
  if (params?.page_size) searchParams.set("page_size", String(params.page_size));
  if (params?.unread_only) searchParams.set("unread_only", "true");
  const response = await api.get<NotificationListResponse>(
    `/notifications?${searchParams.toString()}`,
  );
  return response.data;
};

export const getUnreadNotificationCount = async (): Promise<number> => {
  const response = await api.get<{ count: number }>(
    "/notifications/unread-count",
  );
  return response.data.count;
};

export const markNotificationRead = async (
  id: string,
): Promise<NotificationRow> => {
  const response = await api.post<NotificationRow>(
    `/notifications/${id}/read`,
  );
  return response.data;
};

export const markAllNotificationsRead = async (): Promise<number> => {
  const response = await api.post<{ updated: number }>(
    "/notifications/read-all",
  );
  return response.data.updated;
};

export const getNotificationPreferences = async (): Promise<boolean> => {
  const response = await api.get<{ email_enabled: boolean }>(
    "/notifications/preferences",
  );
  return response.data.email_enabled;
};

export const setNotificationPreferences = async (
  emailEnabled: boolean,
): Promise<boolean> => {
  const response = await api.patch<{ email_enabled: boolean }>(
    "/notifications/preferences",
    { email_enabled: emailEnabled },
  );
  return response.data.email_enabled;
};
