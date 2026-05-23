import Link from "next/link";

export default function Home() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen px-4">
      <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-gray-100 text-center">
        Indic Book Metadata Extractor
      </h1>
      <p className="mt-4 text-zinc-600 dark:text-zinc-400 text-center max-w-md">
        Upload scanned Indic language book PDFs to extract structured metadata.
      </p>
      <div className="flex flex-col sm:flex-row items-center gap-4 mt-8">
        <Link
          href="/upload"
          className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
        >
          Start Upload
        </Link>
        <Link
          href="/library"
          className="px-6 py-3 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors font-medium"
        >
          Browse Library
        </Link>
      </div>
    </div>
  );
}
