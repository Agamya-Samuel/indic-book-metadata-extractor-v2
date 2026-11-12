import Link from "next/link";
import { Card } from "@/components/shared/card";

export function AuthCard({
  title,
  description,
  children,
  footer,
}: {
  title: string;
  description?: React.ReactNode;
  children: React.ReactNode;
  footer?: React.ReactNode;
}) {
  return (
    <div className="flex min-h-[calc(100vh-3.5rem)] items-center justify-center bg-[var(--background)] px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <Link
            href="/"
            className="text-[var(--text-xs)] font-medium uppercase tracking-[0.14em] text-[var(--text-muted)] hover:text-[var(--text)]"
          >
            Indic Books
          </Link>
        </div>
        <Card title={title} description={description}>
          {children}
        </Card>
        {footer && (
          <div className="mt-4 text-center text-[var(--text-sm)] text-[var(--text-muted)]">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}
