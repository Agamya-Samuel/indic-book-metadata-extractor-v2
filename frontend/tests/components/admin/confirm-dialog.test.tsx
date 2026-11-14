import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ConfirmDialog from "@/components/admin/confirm-dialog";

describe("ConfirmDialog", () => {
  it("is announced with its title as the accessible name", () => {
    render(
      <ConfirmDialog
        open
        onClose={() => {}}
        onConfirm={() => {}}
        title="Delete this book?"
        description="This cannot be undone."
      />,
    );

    expect(
      screen.getByRole("dialog", { name: "Delete this book?" }),
    ).toBeDefined();
  });

  it("runs the confirm action", async () => {
    const onConfirm = vi.fn();
    render(
      <ConfirmDialog
        open
        onClose={() => {}}
        onConfirm={onConfirm}
        title="Reset pages?"
        confirmLabel="Reset"
        variant="danger"
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Reset" }));
    expect(onConfirm).toHaveBeenCalled();
  });

  it("keeps the confirm action disabled while it is in flight", async () => {
    const onConfirm = vi.fn();
    render(
      <ConfirmDialog
        open
        loading
        onClose={() => {}}
        onConfirm={onConfirm}
        title="Deleting…"
        confirmLabel="Delete"
      />,
    );

    const confirm = screen.getByRole("button", { name: /Delete/ });
    expect(confirm).toHaveProperty("disabled", true);
    await userEvent.click(confirm);
    expect(onConfirm).not.toHaveBeenCalled();
  });
});