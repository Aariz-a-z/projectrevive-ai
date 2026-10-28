"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Notice } from "@/components/Notice";
import { ApiError, getHealth, uploadReport } from "@/lib/api";
import type { HealthInfo } from "@/lib/types";

const ACCEPTED = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
];

export default function UploadPage() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);

  const [health, setHealth] = useState<HealthInfo | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch((err: unknown) =>
        setHealthError(
          err instanceof ApiError ? err.message : "Could not reach the API.",
        ),
      );
  }, []);

  const maxMb = health?.limits.max_upload_mb ?? 20;

  function choose(next: File | null) {
    setError(null);
    if (!next) {
      setFile(null);
      return;
    }
    const looksAccepted =
      ACCEPTED.includes(next.type) || /\.(pdf|docx)$/i.test(next.name);
    if (!looksAccepted) {
      setError(
        new ApiError(
          0,
          "unsupported_file_type",
          "That looks like neither a PDF nor a DOCX file. Pick a project report in one of those formats.",
        ),
      );
      setFile(null);
      return;
    }
    if (next.size > maxMb * 1024 * 1024) {
      setError(
        new ApiError(
          0,
          "file_too_large",
          `That file is ${(next.size / 1_048_576).toFixed(1)} MB, over the ${maxMb} MB limit.`,
        ),
      );
      setFile(null);
      return;
    }
    setFile(next);
  }

  async function submit() {
    if (!file || busy) return;
    setBusy(true);
    setError(null);
    try {
      const analysis = await uploadReport(file);
      router.push(`/analysis/${analysis.id}`);
    } catch (err: unknown) {
      setError(
        err instanceof ApiError
          ? err
          : new ApiError(0, "unknown", "The upload failed unexpectedly."),
      );
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div className="space-y-1.5">
        <h1 className="text-2xl font-semibold tracking-tight">
          Analyse a project report
        </h1>
        <p className="text-sm leading-relaxed text-muted">
          Upload a PDF or DOCX report, up to {maxMb} MB and{" "}
          {health?.limits.max_pages ?? 300} pages. The file is processed in
          memory and is not stored; the structured analysis is what gets saved.
        </p>
      </div>

      {healthError && (
        <Notice tone="error" title="The analysis API is unreachable">
          {healthError}
        </Notice>
      )}

      {health?.llm.is_mock && (
        <Notice tone="caution" title="Running on the deterministic mock provider">
          No language model is configured, so the analysis will come from
          keyword matching rather than comprehension. It is real output from
          your document, but it is not a real analysis. Set{" "}
          <code className="font-mono text-[11px]">LLM_PROVIDER=anthropic</code>{" "}
          and an API key on the backend for that.
        </Notice>
      )}

      <div
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          choose(event.dataTransfer.files[0] ?? null);
        }}
        className={[
          "rounded-lg border-2 border-dashed p-8 text-center transition-colors",
          dragging
            ? "border-accent bg-accent-soft"
            : "border-border-strong bg-surface",
        ].join(" ")}
      >
        <p className="text-sm font-medium">
          Drop your report here, or choose a file
        </p>
        <p className="mt-1 text-xs text-muted">PDF or DOCX</p>

        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx"
          className="sr-only"
          onChange={(event) => choose(event.target.files?.[0] ?? null)}
        />
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="mt-4 rounded-md border border-border-strong bg-surface px-3 py-1.5 text-sm font-medium hover:bg-surface-muted"
        >
          Choose file
        </button>

        {file && (
          <p className="mt-4 font-mono text-xs break-all text-muted">
            {file.name} &middot; {(file.size / 1024).toFixed(0)} KB
          </p>
        )}
      </div>

      {error && (
        <Notice tone="error" title="That upload was not accepted">
          <p>{error.message}</p>
          {error.detail && (
            <p className="mt-1.5 font-mono text-[11px] break-all opacity-80">
              {error.detail}
            </p>
          )}
        </Notice>
      )}

      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={submit}
          disabled={!file || busy}
          className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-40 dark:text-[#10201c]"
        >
          {busy ? "Analysing…" : "Start analysis"}
        </button>
        {busy && (
          <span className="text-xs text-muted" aria-live="polite">
            Extracting text and building the project profile.
          </span>
        )}
      </div>
    </div>
  );
}
