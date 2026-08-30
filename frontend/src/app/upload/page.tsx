"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useDropzone } from "react-dropzone";
import { useMutation } from "@tanstack/react-query";
import { uploadBook } from "@/lib/api";
import { useBookStore } from "@/stores/book-store";
import { toast } from "sonner";
import { Button } from "@/components/shared/button";
import { Field, Input, Select } from "@/components/shared/input";
import { ErrorState } from "@/components/shared/empty-state";
import { PageContainer, PageHeader, Card, Stack } from "@/components/shared/card";
import { cn } from "@/lib/utils";
import { useDocumentTitle } from "@/hooks/use-document-title";

const LANGUAGES = [
  { value: "tel", label: "Telugu" },
  { value: "hin", label: "Hindi" },
  { value: "eng", label: "English" },
];

export default function UploadPage() {
  useDocumentTitle("Upload book");
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [language, setLanguage] = useState("tel");
  const [error, setError] = useState<string | null>(null);
  const { setLanguage: setStoreLanguage } = useBookStore();

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: { "application/pdf": [".pdf"] },
    maxFiles: 1,
    maxSize: 200 * 1024 * 1024,
    onDrop: (acceptedFiles, fileRejections) => {
      setError(null);
      if (fileRejections.length > 0) {
        const rejection = fileRejections[0];
        if (rejection.errors.some((e) => e.code === "file-too-large")) {
          setError("File exceeds 200 MB limit");
        } else if (rejection.errors.some((e) => e.code === "file-invalid-type")) {
          setError("Only PDF files are accepted");
        } else {
          setError("Invalid file");
        }
        return;
      }
      if (acceptedFiles.length > 0) {
        setFile(acceptedFiles[0]);
      }
    },
  });

  const uploadMutation = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error("No file selected");
      return uploadBook(file, title || undefined, language);
    },
    onSuccess: (data) => {
      setStoreLanguage(language);
      toast.success("Book uploaded successfully");
      router.push(`/books/${data.id}/select-pages`);
    },
    onError: (error: Error) => {
      const msg = error.message || "Failed to upload file";
      setError(msg);
      toast.error(msg);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError("Please select a file");
      return;
    }
    uploadMutation.mutate();
  };

  return (
    <PageContainer>
      <PageHeader
        eyebrow="Step 1 of 7"
        title="Upload a book"
        description="Drop a PDF of an Indic-language book. The system will extract text with OCR, identify bibliographic fields with a fine-tuned language model, and prepare the records for review."
      />

      <div className="mx-auto max-w-2xl">
        <Card>
          <form onSubmit={handleSubmit}>
            <Stack gap={5}>
              <Field label="PDF file" required htmlFor="pdf-file-input">
                <div
                  {...getRootProps()}
                  className={cn(
                    "relative flex flex-col items-center justify-center",
                    "rounded-[var(--radius-lg)] border-2 border-dashed",
                    "px-6 py-10 text-center cursor-pointer",
                    "transition-colors duration-[var(--duration-fast)]",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--background)]",
                    isDragActive
                      ? "border-[var(--accent)] bg-[var(--accent-soft)]"
                      : "border-[var(--border)] hover:border-[var(--border-strong)] hover:bg-[var(--surface-sunken)]",
                  )}
                >
                  <input
                    {...getInputProps({
                      id: "pdf-file-input",
                      name: "pdf",
                      "aria-describedby": "pdf-file-hint",
                    })}
                  />
                  <div
                    aria-hidden="true"
                    className="mb-3 flex size-10 items-center justify-center rounded-full border border-[var(--border)] bg-[var(--surface-raised)] text-[var(--text-muted)]"
                  >
                    <svg
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth={1.5}
                      className="size-5"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 7.5m0 0L7.5 12M12 7.5v9"
                      />
                    </svg>
                  </div>
                  <p className="text-[var(--text-sm)] text-[var(--text)]">
                    <span className="font-semibold text-[var(--accent)]">
                      Click to upload
                    </span>{" "}
                    or drag and drop
                  </p>
                  <p className="mt-1 text-[var(--text-xs)] text-[var(--text-muted)]">
                    PDF up to 200 MB
                  </p>
                  {file && (
                    <p className="mt-3 inline-flex items-center gap-1.5 rounded-full border border-[var(--accent)]/30 bg-[var(--accent-soft)] px-2.5 py-0.5 text-[var(--text-xs)] font-medium text-[var(--accent-soft-text)]">
                      <svg
                        viewBox="0 0 20 20"
                        fill="currentColor"
                        className="size-3"
                        aria-hidden="true"
                      >
                        <path
                          fillRule="evenodd"
                          d="M16.704 5.296a1 1 0 010 1.408l-7.997 8a1 1 0 01-1.408 0l-3.999-4a1 1 0 011.408-1.408L8 12.59l7.296-7.294a1 1 0 011.408 0z"
                          clipRule="evenodd"
                        />
                      </svg>
                      {file.name}
                    </p>
                  )}
                </div>
              </Field>

              <Field
                label="Title"
                hint="Optional. If left blank, the filename is used."
                htmlFor="title"
              >
                <Input
                  id="title"
                  name="title"
                  type="text"
                  autoComplete="off"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g. Kaviraj Margamu"
                />
              </Field>

              <Field label="Primary language" required htmlFor="language">
                <Select
                  id="language"
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                  required
                >
                  {LANGUAGES.map((l) => (
                    <option key={l.value} value={l.value}>
                      {l.label}
                    </option>
                  ))}
                </Select>
              </Field>

              {error && <ErrorState title="Upload failed" description={error} />}

              <div className="flex justify-end pt-2">
                <Button
                  type="submit"
                  size="lg"
                  loading={uploadMutation.isPending}
                  disabled={uploadMutation.isPending}
                >
                  {uploadMutation.isPending ? "Uploading" : "Upload and continue"}
                </Button>
              </div>
            </Stack>
          </form>
        </Card>
      </div>
    </PageContainer>
  );
}
