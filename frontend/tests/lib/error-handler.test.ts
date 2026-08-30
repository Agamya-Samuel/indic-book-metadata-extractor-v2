import { describe, it, expect } from "vitest";
import axios from "axios";
import { parseApiError, getErrorMessage } from "@/lib/error-handler";

function makeAxiosError(
  status: number,
  data?: Record<string, string>,
  message?: string
) {
  const error = new axios.AxiosError(
    message ?? "Request failed",
    status === undefined ? "ERR_NETWORK" : "ERR_BAD_RESPONSE",
    undefined,
    {},
    {
      data: data ?? {},
      status,
      statusText: "Error",
      headers: {},
      config: {} as never,
    }
  );
  return error;
}

describe("parseApiError", () => {
  it("handles connection error (no response)", () => {
    const error = new axios.AxiosError(
      "Network Error",
      "ERR_NETWORK",
      undefined,
      undefined,
      undefined
    );
    const result = parseApiError(error);
    expect(result.status).toBe(0);
    expect(result.message).toContain("Unable to connect");
  });

  it("handles 413 file too large", () => {
    const error = makeAxiosError(413);
    const result = parseApiError(error);
    expect(result.status).toBe(413);
    expect(result.message).toContain("too large");
  });

  it("handles 422 validation error", () => {
    const error = makeAxiosError(422, { detail: "Field required" });
    const result = parseApiError(error);
    expect(result.status).toBe(422);
    expect(result.message).toContain("Invalid input");
    expect(result.detail).toBe("Field required");
  });

  it("handles 404 not found", () => {
    const error = makeAxiosError(404);
    const result = parseApiError(error);
    expect(result.status).toBe(404);
    expect(result.message).toContain("not found");
  });

  it("handles 500 server error", () => {
    const error = makeAxiosError(500, { detail: "Internal error" });
    const result = parseApiError(error);
    expect(result.status).toBe(500);
    expect(result.message).toContain("server error");
  });

  it("handles 503 server error", () => {
    const error = makeAxiosError(503);
    const result = parseApiError(error);
    expect(result.status).toBe(503);
    expect(result.message).toContain("server error");
  });

  it("handles generic Error", () => {
    const error = new Error("Something went wrong");
    const result = parseApiError(error);
    expect(result.status).toBe(0);
    expect(result.message).toBe("Something went wrong");
  });

  it("handles unknown error type", () => {
    const result = parseApiError("string error");
    expect(result.status).toBe(0);
    expect(result.message).toContain("unknown error");
  });

  it("handles null error", () => {
    const result = parseApiError(null);
    expect(result.status).toBe(0);
    expect(result.message).toContain("unknown error");
  });
});

describe("getErrorMessage", () => {
  it("returns message string from parseApiError", () => {
    const error = new Error("Test error message");
    expect(getErrorMessage(error)).toBe("Test error message");
  });

  it("returns message for unknown error", () => {
    expect(getErrorMessage(undefined)).toContain("unknown error");
  });
});
