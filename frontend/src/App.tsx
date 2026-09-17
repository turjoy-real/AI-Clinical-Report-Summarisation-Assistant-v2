export default function App() {
  return (
    <div className="min-h-screen">
      <div className="bg-red-700 px-4 py-3 text-center text-sm font-semibold text-white">
        Educational prototype. Not for clinical use. Synthetic patients only.
      </div>
      <main className="mx-auto max-w-3xl p-8">
        <h1 className="text-2xl font-semibold">AI Clinical Report Summarisation Assistant</h1>
        <p className="mt-3 text-slate-600">
          Placeholder UI (Adarsh owns the app). Backend health lives at{" "}
          <code className="rounded bg-slate-100 px-1">/api/health</code>.
        </p>
      </main>
    </div>
  );
}
