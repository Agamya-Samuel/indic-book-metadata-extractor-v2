import AdminNav, { AdminNavLinks } from "@/components/admin/admin-nav";

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-[var(--background)]">
      <AdminNav />
      <div className="lg:grid lg:grid-cols-[240px_minmax(0,1fr)]">
        <aside className="hidden border-r border-[var(--border)] bg-[var(--surface)] lg:block">
          <div className="sticky top-[var(--nav-height)] max-h-[calc(100dvh-var(--nav-height))] overflow-y-auto p-4">
            <p className="mb-3 px-3 text-[length:var(--text-xs)] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">
              Admin
            </p>
            <AdminNavLinks />
          </div>
        </aside>
        <div className="min-w-0">{children}</div>
      </div>
    </div>
  );
}