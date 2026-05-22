export default function Home() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen">
      <h1 className="text-3xl font-bold">Indic Book Metadata Extractor</h1>
      <p className="mt-4 text-zinc-600">
        Upload scanned Indic language book PDFs to extract structured metadata.
      </p>
    </div>
  );
}
