import AdminNav, { AdminNavLinks } from "@/components/admin/admin-nav";

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-0 flex-1 flex-col bg-[var(--background)]">
      <AdminNav />
      <div className="lg:grid lg:min-h-0 lg:flex-1 lg:grid-cols-[240px_minmax(0,1fr)] lg:items-stretch">
        <aside className="hidden border-r border-[var(--border)] bg-[var(--surface)] lg:sticky lg:top-[var(--nav-height)] lg:block lg:h-[calc(100dvh-var(--nav-height))] lg:overflow-y-auto">
          <div className="p-4">
            <p className="mb-3 px-3 text-[length:var(--text-xs)] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">
              Admin
            </p>
            <AdminNavLinks />
          </div>
        </aside>
        <div className="min-h-0 min-w-0">{children}</div>
      </div>
    </div>
  );
}