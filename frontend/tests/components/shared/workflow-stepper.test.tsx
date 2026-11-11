import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import WorkflowStepper from "@/components/shared/workflow-stepper";
import { STEP_ORDER, stepHref, stepMeta } from "@/lib/workflow-state";
import type { StepKey, StepState, WorkflowStep } from "@/lib/workflow-state";

function makeSteps(states: Partial<Record<StepKey, StepState>>): WorkflowStep[] {
  return STEP_ORDER.map((key) => ({
    key,
    label: stepMeta(key).label,
    shortLabel: stepMeta(key).shortLabel,
    href: stepHref(key, "book-1"),
    state: states[key] ?? "not_started",
  }));
}

describe("WorkflowStepper", () => {
  it("renders all 7 step labels", () => {
    const { container } = render(
      <WorkflowStepper steps={makeSteps({})} currentStep="pages" />,
    );
    const text = container.textContent ?? "";
    for (const label of [
      "Upload",
      "Select Pages",
      "Preprocessing",
      "OCR",
      "OCR Review",
      "LLM Extraction",
      "Metadata Review",
    ]) {
      expect(text).toContain(label);
    }
  });

  it("marks the current step with aria-current", () => {
    const { container } = render(
      <WorkflowStepper
        steps={makeSteps({ upload: "complete", pages: "current" })}
        currentStep="pages"
      />,
    );
    const current = container.querySelector('[aria-current="step"]');
    expect(current).not.toBeNull();
    expect(current?.getAttribute("data-state")).toBe("current");
  });

  it("renders unlocked steps as links and locked steps as spans", () => {
    const steps = makeSteps({
      upload: "complete",
      pages: "complete",
      preprocessing: "current",
    });
    steps[5].state = "not_started";
    const { container } = render(
      <WorkflowStepper steps={steps} currentStep="preprocessing" />,
    );
    expect(container.querySelectorAll("a").length).toBe(3);
    const locked = container.querySelectorAll('[aria-disabled="true"]');
    expect(locked.length).toBeGreaterThan(0);
  });

  it("marks failed and stale steps", () => {
    const { container } = render(
      <WorkflowStepper
        steps={makeSteps({
          upload: "complete",
          pages: "complete",
          preprocessing: "complete",
          ocr: "failed",
          llm: "stale",
        })}
        currentStep="ocr"
      />,
    );
    expect(container.querySelector('[data-state="failed"]')).not.toBeNull();
    expect(container.querySelector('[data-state="stale"]')).not.toBeNull();
  });

  it("renders a detail hint for running steps", () => {
    const steps = makeSteps({ ocr: "current" });
    steps[3].detail = "Reading pages…";
    const { container } = render(
      <WorkflowStepper steps={steps} currentStep="ocr" />,
    );
    expect(container.textContent).toContain("Reading pages…");
  });
});