"use client";

import { useState } from "react";
import {
  PageContainer,
  PageHeader,
  Card,
  Stack,
  type PageLayout,
} from "@/components/shared/card";
import { Button, LinkButton } from "@/components/shared/button";
import { Input, Textarea, Select, Field } from "@/components/shared/input";
import { Chip, type ChipTone } from "@/components/shared/chip";
import { Toolbar, ToolbarGroup } from "@/components/shared/toolbar";
import StatusBadge from "@/components/shared/status-badge";
import { Progress, type ProgressTone } from "@/components/shared/progress";
import JobProgressCard from "@/components/shared/job-progress-card";
import { EmptyState, ErrorState, Banner } from "@/components/shared/empty-state";
import { DataTable, type DataTableColumn } from "@/components/shared/data-table";
import SaveBar from "@/components/shared/save-bar";
import StatCard from "@/components/shared/stat-card";
import Pagination from "@/components/shared/pagination";
import SliderControl from "@/components/shared/slider-control";
import CollapsibleSection from "@/components/shared/collapsible-section";
import { Switch } from "@/components/shared/switch";
import {
  Skeleton,
  SkeletonTable,
  SkeletonImage,
  SkeletonFormField,
} from "@/components/shared/skeleton";
import { Spinner } from "@/components/shared/spinner";
import { StepMarker } from "@/components/shared/step-marker";
import { StageRail } from "@/components/shared/stage-rail";
import type {
  StepState,
  WorkflowProcessing,
  WorkflowStep,
} from "@/lib/workflow-state";
import { useDocumentTitle } from "@/hooks/use-document-title";

const PlusIcon = (
  <svg viewBox="0 0 20 20" fill="currentColor" className="size-4" aria-hidden="true">
    <path d="M10.75 4.75a.75.75 0 00-1.5 0v4.5h-4.5a.75.75 0 000 1.5h4.5v4.5a.75.75 0 001.5 0v-4.5h4.5a.75.75 0 000-1.5h-4.5v-4.5z" />
  </svg>
);

const CHIP_TONES: ChipTone[] = [
  "neutral",
  "accent",
  "success",
  "warning",
  "danger",
  "info",
];

const JOB_STATUSES = ["queued", "running", "completed", "failed", "cancelled"];
const STAGE_STATUSES = [
  "initiated",
  "processing",
  "completed",
  "failed",
  "cancelled",
] as const;
const PROGRESS_TONES: ProgressTone[] = ["accent", "success", "warning", "danger"];
const STEP_STATES: StepState[] = [
  "not_started",
  "current",
  "complete",
  "failed",
  "stale",
];

const LAYOUTS: PageLayout[] = ["reading", "workspace", "gallery"];

const SAMPLE_STEPS: WorkflowStep[] = [
  { key: "upload", label: "Upload", shortLabel: "Upload", href: "/upload", state: "complete" },
  { key: "pages", label: "Select Pages", shortLabel: "Pages", href: "#", state: "complete" },
  { key: "preprocessing", label: "Preprocessing", shortLabel: "Preprocess", href: "#", state: "complete" },
  { key: "ocr", label: "OCR", shortLabel: "OCR", href: "#", state: "current", detail: "Reading pages..." },
  { key: "ocr_review", label: "OCR Review", shortLabel: "Review", href: "#", state: "not_started" },
  { key: "llm", label: "LLM Extraction", shortLabel: "LLM", href: "#", state: "not_started" },
  { key: "review", label: "Metadata Review", shortLabel: "Metadata", href: "#", state: "not_started" },
];

const PROBLEM_STEPS: WorkflowStep[] = SAMPLE_STEPS.map((step) => {
  if (step.key === "ocr") return { ...step, state: "complete" as StepState, detail: undefined };
  if (step.key === "llm") return { ...step, state: "failed" as StepState };
  if (step.key === "review") return { ...step, state: "stale" as StepState };
  return step;
}).filter((step) => step.key !== "ocr_review");

const SAMPLE_PROCESSING: WorkflowProcessing = {
  kind: "ocr",
  job: null,
  progress: 42,
};

interface SampleRow {
  id: string;
  title: string;
  language: string;
  status: string;
  pages: number;
}

const SAMPLE_ROWS: SampleRow[] = [
  { id: "1", title: "Veerendra Bhatia — Selected Poems", language: "Hindi", status: "awaiting_review", pages: 119 },
  { id: "2", title: "Kaviraj Margamu", language: "Telugu", status: "complete", pages: 84 },
  { id: "3", title: "Single-origin verification book", language: "Hindi", status: "uploaded", pages: 119 },
];

const SAMPLE_COLUMNS: DataTableColumn<SampleRow>[] = [
  { key: "title", header: "Book", cell: (row) => row.title },
  { key: "language", header: "Language", cell: (row) => row.language, hideBelow: "sm" },
  {
    key: "status",
    header: "Status",
    cell: (row) => <StatusBadge status={row.status} />,
  },
  {
    key: "pages",
    header: "Pages",
    cell: (row) => <span className="tabular-nums">{row.pages}</span>,
    hideBelow: "md",
  },
];

function Section({
  title,
  description,
  children,
  className,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <Card title={title} description={description} className={className}>
      <div className="flex flex-wrap items-center gap-3">{children}</div>
    </Card>
  );
}

/** One example of every primitive and pattern, in its states. */
export default function DesignKitPage() {
  useDocumentTitle("Design kit");
  const [dirtyCount, setDirtyCount] = useState(0);
  const [saving, setSaving] = useState(false);
  const [showSaveBar, setShowSaveBar] = useState(false);
  const [slider, setSlider] = useState(25);
  const [switchOn, setSwitchOn] = useState(true);
  const [page, setPage] = useState(2);
  const [layout, setLayout] = useState<PageLayout>("reading");

  return (
    <PageContainer layout={layout} className="pb-24">
      <PageHeader
        eyebrow="Admin · Reference"
        title="Design kit"
        description="Every shared primitive in its states. This page is the living reference for the composition layer (plans/008) — if a screen needs a pattern that is not here, add it here first."
        actions={
          <ToolbarGroup>
            {LAYOUTS.map((value) => (
              <Button
                key={value}
                variant={layout === value ? "secondary" : "ghost"}
                size="sm"
                onClick={() => setLayout(value)}
              >
                {value}
              </Button>
            ))}
          </ToolbarGroup>
        }
      />

      <Stack gap={6}>
        <Section
          title="Buttons"
          description="Variants, sizes, and pending/disabled states."
        >
          {(["primary", "secondary", "outline", "ghost", "danger", "link"] as const).map(
            (variant) => (
              <Button key={variant} variant={variant} size="sm">
                {variant}
              </Button>
            ),
          )}
          <span className="mx-2 h-6 w-px bg-[var(--border)]" aria-hidden="true" />
          {(["sm", "md", "lg"] as const).map((size) => (
            <Button key={size} size={size}>
              {size}
            </Button>
          ))}
          <span className="mx-2 h-6 w-px bg-[var(--border)]" aria-hidden="true" />
          <Button loading>Loading</Button>
          <Button disabled>Disabled</Button>
          <Button leftIcon={PlusIcon}>With icon</Button>
          <LinkButton href="/admin/design" variant="outline">
            Link button
          </LinkButton>
        </Section>

        <Section title="Chips" description="Counts, states, identifiers.">
          {CHIP_TONES.map((tone) => (
            <Chip key={tone} tone={tone} dot>
              {tone}
            </Chip>
          ))}
          <Chip mono>P1476</Chip>
          <Chip tone="success">{`4 of 9`}</Chip>
        </Section>

        <Section
          title="Status badges"
          description="Job statuses and stage statuses."
        >
          {JOB_STATUSES.map((status) => (
            <StatusBadge key={status} status={status} />
          ))}
          <span className="mx-2 h-6 w-px bg-[var(--border)]" aria-hidden="true" />
          {STAGE_STATUSES.map((status) => (
            <StatusBadge key={status} status="" stageStatus={status} />
          ))}
        </Section>

        <Section
          title="Step markers"
          description="The stage-rail disc, one per state."
        >
          {STEP_STATES.map((state, i) => (
            <span key={state} className="flex items-center gap-2">
              <StepMarker state={state} index={i} size="md" />
              <span className="text-[length:var(--text-xs)] text-[var(--text-muted)]">
                {state}
              </span>
            </span>
          ))}
          <span className="flex items-center gap-2">
            <StepMarker state="current" index={3} busy size="md" />
            <span className="text-[length:var(--text-xs)] text-[var(--text-muted)]">
              current · busy
            </span>
          </span>
        </Section>

        <Section
          title="Layout modes"
          description="PageContainer: reading (content-max), workspace and gallery (full-bleed)."
        >
          <span className="text-[length:var(--text-sm)] text-[var(--text-muted)]">
            Active: <span className="font-mono">{layout}</span>
          </span>
        </Section>

        <Card title="Toolbar" description="Workspace control bar with grouped clusters.">
          <Toolbar sticky={false}>
            <ToolbarGroup>
              <Button variant="outline" size="sm">
                Previous
              </Button>
              <span className="px-2 text-[length:var(--text-sm)] tabular-nums text-[var(--text-muted)]">
                Page 3 of 119
              </span>
              <Button variant="outline" size="sm">
                Next
              </Button>
            </ToolbarGroup>
            <ToolbarGroup align="end">
              <Chip dot tone="warning">
                12 low confidence
              </Chip>
              <Button size="sm">Save corrections</Button>
            </ToolbarGroup>
          </Toolbar>
        </Card>

        <Card title="Fields" description="Input, textarea, select, with hint and error.">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Title" hint="Optional. Defaults to the filename." htmlFor="kit-title">
              <Input id="kit-title" placeholder="e.g. Kaviraj Margamu" />
            </Field>
            <Field label="Language" required htmlFor="kit-language">
              <Select id="kit-language" defaultValue="tel">
                <option value="tel">Telugu</option>
                <option value="hin">Hindi</option>
              </Select>
            </Field>
            <Field
              label="ISBN"
              error="Not a valid ISBN-13."
              htmlFor="kit-isbn"
              className="sm:col-span-2"
            >
              <Input id="kit-isbn" defaultValue="978" />
            </Field>
            <Field label="Description" htmlFor="kit-desc" className="sm:col-span-2">
              <Textarea id="kit-desc" rows={3} placeholder="Long text field" />
            </Field>
          </div>
        </Card>

        <Section title="Progress" description="0–100 contract, tones, indeterminate.">
          <div className="w-full space-y-3">
            {PROGRESS_TONES.map((tone) => (
              <Progress key={tone} value={62} tone={tone} label={tone} showValue />
            ))}
            <Progress indeterminate label="Indeterminate" />
          </div>
        </Section>

        <Card title="Job progress card" description="Running and failed states.">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <JobProgressCard
              title="Running OCR"
              progress={42}
              status="running"
              phase="Reading page 12 of 119"
              itemLabel="Page 12 of 119"
              elapsedMs={95_000}
              onCancel={() => {}}
            />
            <JobProgressCard
              title="Extraction failed"
              progress={61}
              status="failed"
              error="Ollama is unreachable."
              onRetry={() => {}}
            />
          </div>
        </Card>

        <Card title="Stage rail" description="Sticky left navigation for a book (plans/008 Phase 1).">
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div>
              <p className="mb-2 text-[length:var(--text-xs)] uppercase tracking-wider text-[var(--text-muted)]">
                Mid-run, with a monitor sub-row
              </p>
              <StageRail
                steps={SAMPLE_STEPS}
                currentStep="ocr"
                processing={SAMPLE_PROCESSING}
              />
            </div>
            <div>
              <p className="mb-2 text-[length:var(--text-xs)] uppercase tracking-wider text-[var(--text-muted)]">
                Failed and out-of-date stages
              </p>
              <StageRail steps={PROBLEM_STEPS} currentStep="llm" />
            </div>
          </div>
        </Card>

        <Card title="Stat cards" description="Standalone and flush (inside a divided card).">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <StatCard label="Total books" value={2} sublabel="in your library" />
            <StatCard label="Complete" value={0} tone="success" />
            <StatCard label="Awaiting review" value={1} tone="warning" />
            <StatCard label="Failed jobs" value={4} tone="danger" />
          </div>
        </Card>

        <Card title="Table" description="DataTable with sticky header and empty/loading states.">
          <Stack gap={4}>
            <DataTable
              columns={SAMPLE_COLUMNS}
              rows={SAMPLE_ROWS}
              rowKey={(row) => row.id}
              caption="Sample books"
              stickyHeader
              maxHeight={220}
            />
            <DataTable
              columns={SAMPLE_COLUMNS}
              rows={[]}
              rowKey={(row) => row.id}
              empty={
                <EmptyState
                  title="No books match"
                  description="Clear the filters to see everything."
                />
              }
            />
            <DataTable columns={SAMPLE_COLUMNS} rows={[]} rowKey={(row) => row.id} loading />
          </Stack>
        </Card>

        <Section title="Pagination">
          <Pagination page={page} totalPages={8} onPageChange={setPage} />
        </Section>

        <Card title="States" description="Empty, error, and the five banner tones.">
          <Stack gap={3}>
            <EmptyState
              title="No pages to select"
              description="Pick the pages you want to process."
              action={<Button size="sm">Select pages</Button>}
            />
            <ErrorState title="Could not save" description="The server rejected the change." />
            {(["danger", "info", "success", "warning", "neutral"] as const).map((tone) => (
              <Banner key={tone} tone={tone}>
                {tone} banner — inline, non-blocking feedback.
              </Banner>
            ))}
          </Stack>
        </Card>

        <Card title="Collapsible section" description="Used for field groups and prompt editors.">
          <CollapsibleSection title="Core Identity" count={9} defaultOpen>
            <p className="text-[length:var(--text-sm)] text-[var(--text-muted)]">
              Grouped content lives here.
            </p>
          </CollapsibleSection>
        </Card>

        <Card title="Controls" description="Slider, switch, and spinner.">
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
            <SliderControl
              label="Brightness"
              value={slider}
              min={-100}
              max={100}
              onChange={setSlider}
              hint="—100 to 100"
            />
            <div className="flex items-center gap-4">
              <Switch
                label="Example preference"
                checked={switchOn}
                onCheckedChange={setSwitchOn}
              />
              <span className="text-[length:var(--text-sm)] text-[var(--text-muted)]">
                Preference switch
              </span>
            </div>
            <div className="flex items-center gap-4">
              <Spinner className="size-5 text-[var(--accent-text)]" />
              <span className="text-[length:var(--text-sm)] text-[var(--text-muted)]">
                Spinner, size-5
              </span>
            </div>
          </div>
        </Card>

        <Card title="Skeletons" description="First-load placeholders, not spinners.">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <SkeletonTable rows={3} />
            <div className="grid grid-cols-2 gap-3">
              <SkeletonImage />
              <div className="space-y-3">
                <SkeletonFormField />
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-4 w-40" />
              </div>
            </div>
          </div>
        </Card>

        <Card title="Save bar" description="Sticky bottom bar with the unsaved-changes guard.">
          <Stack gap={3}>
            <p className="text-[length:var(--text-sm)] text-[var(--text-muted)]">
              The bar is fixed to the viewport bottom, so it is only mounted on
              demand here. In a real screen it appears when there are unsaved
              changes.
            </p>
            <ToolbarGroup>
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  setDirtyCount((n) => n + 1);
                  setShowSaveBar(true);
                }}
              >
                Make a change
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => {
                  setDirtyCount(0);
                  setShowSaveBar(false);
                }}
              >
                Reset
              </Button>
            </ToolbarGroup>
          </Stack>
        </Card>
      </Stack>

      {showSaveBar && (
        <SaveBar
          dirtyCount={dirtyCount}
          saving={saving}
          onSave={() => {
            setSaving(true);
            window.setTimeout(() => {
              setSaving(false);
              setDirtyCount(0);
            }, 800);
          }}
          onDiscard={() => {
            setDirtyCount(0);
            setShowSaveBar(false);
          }}
          extraActions={<Chip tone="info">{`layout: ${layout}`}</Chip>}
        />
      )}
    </PageContainer>
  );
}
