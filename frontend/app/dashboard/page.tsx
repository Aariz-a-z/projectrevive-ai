"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  IconDoc,
  IconSearch,
  IconTrash,
  IconUpload,
} from "@/components/icons";
import {
  Badge,
  Button,
  Notice,
  Panel,
  PanelHeader,
  StatTile,
} from "@/components/ui";
import { ApiError, deleteAnalysis, getHealth, listAnalyses, uploadReport } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type { AnalysisSummary, HealthInfo } from "@/lib/types";

export default function DashboardPage() {
  const { user, ready } = useRequireAuth();
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);

  const [health, setHealth] = useState<HealthInfo | null>(null);
  const [analyses, setAnalyses] = useState<AnalysisSummary[] | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const refresh = useCallback(() => {
    listAnalyses()
      .then(setAnalyses)
      .catch(() => setAnalyses([]));
  }, []);

  useEffect(() => {
    if (!ready) return;
    getHealth().then(setHealth).catch(() => undefined);
    refresh();
  }, [ready, refresh]);

  const maxMb = health?.limits.max_upload_mb ?? 20;

  function choose(next: File | null) {
    setError(null);
    if (!next) return setFile(null);

    if (!/\.(pdf|docx)$/i.test(next.name)) {
      setError(
        new ApiError(
          0,
          "unsupported_file_type",
          "That is neither a PDF nor a DOCX file. Pick a project report in one of those formats.",
        ),
      );
      return setFile(null);
    }
    if (next.size > maxMb * 1024 * 1024) {
      setError(
        new ApiError(
          0,
          "file_too_large",
          `That file is ${(next.size / 1_048_576).toFixed(1)} MB, over the ${maxMb} MB limit.`,
        ),
      );
      return setFile(null);
    }
    setFile(next);
  }

  async function analyse() {
    if (!file || busy) return;
    setBusy(true);
    setError(null);
    try {
      const created = await uploadReport(file);
      router.push(`/analysis/${created.id}`);
    } catch (err: unknown) {
      setError(
        err instanceof ApiError
          ? err
          : new ApiError(0, "unknown", "The upload failed unexpectedly."),
      );
      setBusy(false);
    }
  }

  async function remove(id: string) {
    setAnalyses((rows) => rows?.filter((r) => r.id !== id) ?? null);
    try {
      await deleteAnalysis(id);
    } catch {
      refresh();
    }
  }

  if (!ready) {
    return (
      <div className="space-y-4" aria-busy="true">
        <div className="h-10 w-56 animate-pulse rounded-lg bg-panel-inset" />
        <div className="h-64 animate-pulse rounded-xl bg-panel-inset" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="mt-1 text-sm text-muted">
            Signed in as <span className="text-fg-dim">{user?.email}</span>
          </p>
        </div>
        <div className="grid w-full grid-cols-3 gap-2 sm:w-auto sm:min-w-[300px]">
          <StatTile value={analyses?.length ?? "—"} label="Analyses" />
          <StatTile
            value={`${maxMb} MB`}
            label="Upload limit"
            accent="violet"
          />
          <StatTile
            value={health?.limits.max_pages ?? "—"}
            label="Max pages"
            accent="blue"
          />
        </div>
      </div>

      {health?.llm.is_mock && (
        <Notice tone="caution" title="No language model is configured">
          Project profiles come from keyword matching rather than
          comprehension. Weakness and gap detection still works fully, since
          those rules need no model. Set{" "}
          <code>LLM_PROVIDER=anthropic</code> and an API key on the backend for
          the model&rsquo;s contribution.
        </Notice>
      )}

      <div className="grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
        <Panel>
          <PanelHeader title="Analyse a report" icon={<IconUpload />} />
          <div className="space-y-4 p-4">
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragging(false);
                choose(e.dataTransfer.files[0] ?? null);
              }}
              className={`rounded-xl border-2 border-dashed p-8 text-center transition-colors ${
                dragging
                  ? "border-cyan bg-cyan-soft/40"
                  : "border-edge-bright bg-panel-inset"
              }`}
            >
              <span className="mx-auto mb-3 grid h-11 w-11 place-items-center rounded-xl bg-panel p-2.5 text-cyan ring-1 ring-edge">
                <IconDoc />
              </span>
              <p className="text-sm font-medium">
                Drop a report here, or choose a file
              </p>
              <p className="mt-1 text-xs text-muted">
                PDF or DOCX · processed in memory, never written to disk
              </p>

              <input
                ref={inputRef}
                type="file"
                accept=".pdf,.docx"
                className="sr-only"
                onChange={(e) => choose(e.target.files?.[0] ?? null)}
              />
              <Button
                variant="ghost"
                className="mt-4"
                onClick={() => inputRef.current?.click()}
              >
                Choose file
              </Button>

              {file && (
                <p className="mt-4 font-mono text-xs break-all text-fg-dim">
                  {file.name} · {(file.size / 1024).toFixed(0)} KB
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
              <Button onClick={analyse} disabled={!file || busy}>
                {busy ? "Analysing…" : "Start analysis"}
              </Button>
              {busy && (
                <span className="text-xs text-muted" aria-live="polite">
                  Extracting text and building the project profile.
                </span>
              )}
            </div>
          </div>
        </Panel>

        <Panel>
          <PanelHeader
            title="Your analyses"
            icon={<IconSearch />}
            accent="violet"
            right={
              analyses ? (
                <Badge accent="violet">{analyses.length}</Badge>
              ) : undefined
            }
          />
          <div className="p-4">
            {analyses === null && (
              <div className="space-y-2" aria-busy="true">
                <div className="h-14 animate-pulse rounded-lg bg-panel-inset" />
                <div className="h-14 animate-pulse rounded-lg bg-panel-inset" />
              </div>
            )}

            {analyses?.length === 0 && (
              <p className="py-8 text-center text-sm text-muted">
                Nothing analysed yet. Upload a report to get started.
              </p>
            )}

            {analyses && analyses.length > 0 && (
              <ul className="space-y-2">
                {analyses.map((row) => (
                  <li
                    key={row.id}
                    className="panel-inset group flex items-center gap-3 rounded-lg p-3"
                  >
                    <Link href={`/analysis/${row.id}`} className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium group-hover:text-cyan">
                        {row.title ?? row.filename}
                      </p>
                      <p className="mt-0.5 truncate font-mono text-[11px] text-muted">
                        {row.filename} · {row.page_count}p ·{" "}
                        {new Date(row.created_at).toLocaleDateString()}
                      </p>
                    </Link>
                    {row.provenance.is_mock && <Badge accent="amber">mock</Badge>}
                    <button
                      type="button"
                      onClick={() => remove(row.id)}
                      title="Delete this analysis"
                      className="rounded-md p-1.5 text-muted hover:bg-rose-soft hover:text-rose"
                    >
                      <IconTrash className="h-4 w-4" />
                      <span className="sr-only">Delete {row.filename}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Panel>
      </div>
    </div>
  );
}
