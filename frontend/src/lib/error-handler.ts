import axios from "axios";
import { toast } from "@/lib/toast";

interface ApiError {
  message: string;
  status: number;
  detail?: string;
}

export function parseApiError(error: unknown): ApiError {
  if (axios.isAxiosError(error)) {
    const status = error.response?.status ?? 0;
    const detail =
      error.response?.data?.detail ??
      error.response?.data?.message ??
      null;

    if (status === 0) {
      return {
        message: "Unable to connect to the server. Please check your connection.",
        status: 0,
      };
    }

    if (status === 413) {
      return {
        message: "File is too large. Please upload a smaller file.",
        status,
        detail: detail ?? undefined,
      };
    }

    if (status === 422) {
      return {
        message: "Invalid input. Please check your data and try again.",
        status,
        detail: detail ?? undefined,
      };
    }

    if (status === 404) {
      return {
        message: "The requested resource was not found.",
        status,
        detail: detail ?? undefined,
      };
    }

    if (status && status >= 500) {
      return {
        message: "A server error occurred. Please try again later.",
        status,
        detail: detail ?? undefined,
      };
    }

    return {
      message: detail ?? error.message ?? "An unexpected error occurred.",
      status,
      detail: detail ?? undefined,
    };
  }

  if (error instanceof Error) {
    return {
      message: error.message,
      status: 0,
    };
  }

  return {
    message: "An unknown error occurred.",
    status: 0,
  };
}

export function getErrorMessage(error: unknown): string {
  return parseApiError(error).message;
}

/**
 * Surface an error once, as a toast, and return the message so callers can
 * also keep it inline if they need to. Use this instead of hand-rolling
 * `toast.error(getErrorMessage(err))` so error copy stays consistent.
 */
export function toastError(error: unknown, fallback?: string): string {
  const parsed = parseApiError(error);
  const message = parsed.message || fallback || "An unexpected error occurred.";
  toast.error(message);
  return message;
}
