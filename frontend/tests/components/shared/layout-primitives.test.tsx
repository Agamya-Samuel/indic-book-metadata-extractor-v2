import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { PageContainer, Card } from "@/components/shared/card";
import { Chip } from "@/components/shared/chip";
import { Toolbar, ToolbarGroup } from "@/components/shared/toolbar";
import { StepMarker } from "@/components/shared/step-marker";
import { StageRail } from "@/components/shared/stage-rail";
import { DataTable } from "@/components/shared/data-table";
import { STEP_ORDER, stepHref, stepMeta } from "@/lib/workflow-state";
import type {
  StepKey,
  StepState,
  WorkflowProcessing,
  WorkflowStep,
} from "@/lib/workflow-state";

function makeSteps(states: Partial<Record<StepKey, StepState>>): WorkflowStep[] {
  return STEP_ORDER.map((key) => ({
    key,
    label: stepMeta(key).label,
    shortLabel: stepMeta(key).shortLabel,
    href: stepHref(key, "book-1"),
    state: states[key] ?? "not_started",
  }));
}

describe("PageContainer layout modes", () => {
  it("defaults to the reading column", () => {
    const { container } = render(<PageContainer>x</PageContainer>);
    const cls = container.firstElementChild?.className ?? "";
    expect(cls).toContain("max-w-[var(--content-max)]");
    expect(cls).toContain("mx-auto");
  });

  it("workspace and gallery go full-bleed", () => {
    for (const layout of ["workspace", "gallery"] as const) {
      const { container } = render(
        <PageContainer layout={layout}>x</PageContainer>,
      );
      const cls = container.firstElementChild?.className ?? "";
      expect(cls).toContain("w-full");
      expect(cls).not.toContain("max-w-[var(--content-max)]");
    }
  });

  it("merges a caller className", () => {
    const { container } = render(
      <PageContainer className="pb-24">x</PageContainer>,
    );
    expect(container.firstElementChild?.className).toContain("pb-24");
  });
});

describe("Chip", () => {
  it("renders its label with the neutral tone by default", () => {
    const { container } = render(<Chip>3 of 9</Chip>);
    const chip = container.firstElementChild as HTMLElement;
    expect(chip.textContent).toBe("3 of 9");
    expect(chip.className).toContain("surface-sunken");
  });

  it("applies a tone and renders the leading dot", () => {
    const { container } = render(<Chip tone="success" dot>ok</Chip>);
    const chip = container.firstElementChild as HTMLElement;
    expect(chip.className).toContain("success-50");
    const dot = chip.querySelector('[aria-hidden="true"]');
    expect(dot).not.toBeNull();
  });

  it("renders identifiers in monospace", () => {
    const { container } = render(<Chip mono>P1476</Chip>);
    expect((container.firstElementChild as HTMLElement).className).toContain(
      "font-mono",
    );
  });
});

describe("Toolbar", () => {
  it("renders children and supports a sticky bar", () => {
    const { container } = render(
      <Toolbar sticky>
        <ToolbarGroup align="end">right</ToolbarGroup>
      </Toolbar>,
    );
    const bar = container.firstElementChild as HTMLElement;
    expect(bar.className).toContain("sticky");
    expect(bar.textContent).toContain("right");
    expect((bar.firstElementChild as HTMLElement).className).toContain("ml-auto");
  });
});

describe("StepMarker", () => {
  it("shows a check for a complete stage", () => {
    const { container } = render(<StepMarker state="complete" index={0} />);
    const marker = container.firstElementChild as HTMLElement;
    expect(marker.className).toContain("success-600");
    expect(marker.querySelector("svg")).not.toBeNull();
  });

  it("shows the glyphs for failed and stale", () => {
    const failed = render(<StepMarker state="failed" index={2} />);
    expect(failed.container.textContent).toBe("!");
    const stale = render(<StepMarker state="stale" index={3} />);
    expect(stale.container.textContent).toBe("↻");
  });

  it("shows the position number for the current stage, or a spinner when busy", () => {
    const idle = render(<StepMarker state="current" index={3} />);
    expect(idle.container.textContent).toBe("4");

    const busy = render(<StepMarker state="current" index={3} busy />);
    const spinner = busy.container.querySelector("svg.animate-spin");
    expect(spinner).not.toBeNull();
  });

  it("numbers a not-started stage", () => {
    const { container } = render(<StepMarker state="not_started" index={6} />);
    expect(container.textContent).toBe("7");
  });
});

describe("StageRail", () => {
  it("renders every stage and marks the current one", () => {
    const { container } = render(
      <StageRail
        steps={makeSteps({ upload: "complete", pages: "current" })}
        currentStep="pages"
      />,
    );
    for (const key of STEP_ORDER) {
      expect(container.textContent).toContain(stepMeta(key).label);
    }
    const current = container.querySelector('[aria-current="step"]');
    expect(current).not.toBeNull();
    expect(current?.getAttribute("href")).toBe(stepHref("pages", "book-1"));
  });

  it("locks stages that have not started", () => {
    const { container } = render(
      <StageRail steps={makeSteps({})} currentStep="upload" />,
    );
    expect(container.querySelectorAll('[aria-disabled="true"]').length).toBe(
      STEP_ORDER.length,
    );
    expect(container.querySelectorAll("a").length).toBe(0);
  });

  it("renders a monitor sub-row under the stage that owns the job", () => {
    const steps = makeSteps({ upload: "complete", pages: "complete", ocr: "current" });
    steps[3].detail = "Reading pages...";
    const processing: WorkflowProcessing = {
      kind: "ocr",
      job: null,
      progress: 42,
    };
    const { container } = render(
      <StageRail steps={steps} currentStep="ocr" processing={processing} />,
    );
    expect(container.textContent).toContain("Reading pages...");
    expect(container.textContent).toContain("42%");
  });

  it("does not render a sub-row when nothing is processing", () => {
    const { container } = render(
      <StageRail
        steps={makeSteps({ ocr: "current" })}
        currentStep="ocr"
        processing={null}
      />,
    );
    expect(container.textContent).not.toContain("%");
  });
});

interface Row {
  id: string;
  title: string;
  status: string;
}

const COLUMNS = [
  { key: "title", header: "Book", cell: (row: Row) => row.title },
  { key: "status", header: "Status", cell: (row: Row) => row.status },
];

const ROWS: Row[] = [
  { id: "1", title: "Kaviraj Margamu", status: "complete" },
  { id: "2", title: "Selected Poems", status: "uploaded" },
];

describe("DataTable states", () => {
  it("renders headers and rows", () => {
    const { container } = render(
      <DataTable columns={COLUMNS} rows={ROWS} rowKey={(row) => row.id} />,
    );
    expect(container.querySelectorAll("thead th").length).toBe(2);
    expect(container.querySelectorAll("tbody tr").length).toBe(2);
    expect(container.textContent).toContain("Kaviraj Margamu");
  });

  it("renders a skeleton instead of the table while loading", () => {
    const { container } = render(
      <DataTable
        columns={COLUMNS}
        rows={[]}
        rowKey={(row) => row.id}
        loading
      />,
    );
    expect(container.querySelector("table")).toBeNull();
    expect(container.querySelector(".animate-pulse")).not.toBeNull();
  });

  it("renders the provided empty state only when rows are empty", () => {
    const empty = <p>Nothing here</p>;
    const withRows = render(
      <DataTable
        columns={COLUMNS}
        rows={ROWS}
        rowKey={(row) => row.id}
        empty={empty}
      />,
    );
    expect(withRows.container.textContent).not.toContain("Nothing here");

    const withoutRows = render(
      <DataTable
        columns={COLUMNS}
        rows={[]}
        rowKey={(row) => row.id}
        empty={empty}
      />,
    );
    expect(withoutRows.container.textContent).toContain("Nothing here");
  });

  it("pins the header when asked", () => {
    const { container } = render(
      <DataTable
        columns={COLUMNS}
        rows={ROWS}
        rowKey={(row) => row.id}
        stickyHeader
      />,
    );
    expect(container.querySelector("thead")?.className).toContain("sticky");
  });
});

describe("Card", () => {
  it("renders a header and body", () => {
    const { container } = render(
      <Card title="Metadata" description="Grouped by category.">
        body
      </Card>,
    );
    expect(container.textContent).toContain("Metadata");
    expect(container.textContent).toContain("Grouped by category.");
    expect(container.textContent).toContain("body");
  });
});
