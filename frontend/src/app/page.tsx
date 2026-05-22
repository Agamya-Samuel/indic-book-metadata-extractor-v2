import Link from "next/link";

export default function Home() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen">
      <h1 className="text-3xl font-bold">Indic Book Metadata Extractor</h1>
      <p className="mt-4 text-zinc-600">
        Upload scanned Indic language book PDFs to extract structured metadata.
      </p>
      <div className="flex items-center gap-4 mt-8">
        <Link
          href="/upload"
          className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
        >
          Start Upload
        </Link>
        <Link
          href="/library"
          className="px-6 py-3 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors font-medium"
        >
          Browse Library
        </Link>
      </div>
    </div>
  );
}