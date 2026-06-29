import Link from "next/link";

export default function AppNavbar() {
  return (
    <nav className="bg-white dark:bg-gray-800 border-b dark:border-gray-700 px-4 py-3">
      <div className="max-w-screen-2xl mx-auto flex items-center justify-between">
        <Link href="/" className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          Indic Book Metadata Extractor
        </Link>
        <div className="flex items-center gap-4">
          <Link href="/library" className="text-sm text-blue-600 dark:text-blue-400 hover:underline">
            Library
          </Link>
          <Link href="/bulk-operations" className="text-sm text-blue-600 dark:text-blue-400 hover:underline">
            Bulk Operations
          </Link>
        </div>
      </div>
    </nav>
  );
}
