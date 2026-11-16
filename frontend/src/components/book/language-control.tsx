"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { updateBookLanguage } from "@/lib/api";
import { getErrorMessage } from "@/lib/error-handler";
import { Button } from "@/components/shared/button";
import { Select } from "@/components/shared/input";

const LANGUAGES = [
  { value: "tel", label: "Telugu" },
  { value: "hin", label: "Hindi" },
  { value: "eng", label: "English" },
];

interface BookLanguageControlProps {
  bookId: string;
  language: string;
}

export default function BookLanguageControl({
  bookId,
  language,
}: BookLanguageControlProps) {
  const [value, setValue] = useState(language);
  const queryClient = useQueryClient();
  const router = useRouter();

  const mutation = useMutation({
    mutationFn: () => updateBookLanguage(bookId, value),
    onSuccess: (data) => {
      toast.success(`Language changed to ${data.language}`);
      queryClient.invalidateQueries();
      if (data.job_id) {
        router.push(`/books/${bookId}/ocr-processing`);
      }
    },
    onError: (error: Error) => {
      toast.error(getErrorMessage(error));
    },
  });

  const handleChange = () => {
    if (value === language) return;
    const confirmed = window.confirm(
      "Changing the language clears OCR text produced with the old language and re-runs OCR. Reviewed metadata is kept. Continue?"
    );
    if (confirmed) mutation.mutate();
  };

  return (
    <div className="flex items-center gap-1.5">
      <Select
        aria-label="Book primary language"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        className="h-8 text-[length:var(--text-xs)]"
      >
        {LANGUAGES.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </Select>
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={handleChange}
        loading={mutation.isPending}
        disabled={mutation.isPending || value === language}
      >
        Set language
      </Button>
    </div>
  );
}
