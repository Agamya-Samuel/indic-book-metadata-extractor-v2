import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import MetadataForm from "@/components/metadata/metadata-form";
import type { MetadataFieldDefinition } from "@/lib/api";

const mockFieldDefs: MetadataFieldDefinition[] = [
  {
    field_name: "title",
    display_name: "Title",
    wikidata_property: "P1476",
    batch_group: "core_identity",
  },
  {
    field_name: "author",
    display_name: "Author",
    wikidata_property: "P50",
    batch_group: "core_identity",
  },
  {
    field_name: "publisher",
    display_name: "Publisher",
    wikidata_property: "P123",
    batch_group: "publication",
  },
  {
    field_name: "publication_date",
    display_name: "Publication Date",
    wikidata_property: "P577",
    batch_group: "publication",
  },
  {
    field_name: "description_work",
    display_name: "Description",
    wikidata_property: null,
    batch_group: "core_identity",
  },
];

const defaultValues: Record<string, string> = {
  title: "Test Book Title",
  author: "Test Author",
  publisher: "",
  publication_date: "not found",
  description_work: "",
};

describe("MetadataForm", () => {
  it("renders field group sections", () => {
    render(
      <MetadataForm
        fieldDefinitions={mockFieldDefs}
        values={defaultValues}
        onSave={vi.fn()}
        isSaving={false}
      />
    );
    expect(screen.getByText("Core Identity")).toBeDefined();
    expect(screen.getByText("Publication")).toBeDefined();
  });

  it("renders custom fields section", () => {
    render(
      <MetadataForm
        fieldDefinitions={mockFieldDefs}
        values={defaultValues}
        onSave={vi.fn()}
        isSaving={false}
      />
    );
    expect(screen.getByText(/Custom fields/)).toBeDefined();
  });

  it("pre-fills values from props", () => {
    render(
      <MetadataForm
        fieldDefinitions={mockFieldDefs}
        values={defaultValues}
        onSave={vi.fn()}
        isSaving={false}
      />
    );
    const inputs = screen.getAllByRole("textbox");
    const titleInput = inputs.find(
      (i) => (i as HTMLInputElement).value === "Test Book Title"
    );
    expect(titleInput).toBeDefined();
  });

  it("hands its save and discard actions to the page save bar", () => {
    const onRegisterActions = vi.fn();
    render(
      <MetadataForm
        fieldDefinitions={mockFieldDefs}
        values={defaultValues}
        onSave={vi.fn()}
        isSaving={false}
        onRegisterActions={onRegisterActions}
      />
    );
    expect(onRegisterActions).toHaveBeenCalled();
    const actions = onRegisterActions.mock.calls.at(-1)![0];
    expect(typeof actions.save).toBe("function");
    expect(typeof actions.discard).toBe("function");
    // The form no longer owns a save button; the page's save bar does.
    expect(screen.queryByText(/Save metadata/)).toBeNull();
  });

  it("reports zero unsaved changes initially", () => {
    const onDirtyCountChange = vi.fn();
    render(
      <MetadataForm
        fieldDefinitions={mockFieldDefs}
        values={defaultValues}
        onSave={vi.fn()}
        isSaving={false}
        onDirtyCountChange={onDirtyCountChange}
      />
    );
    expect(onDirtyCountChange).toHaveBeenCalledWith(0);
  });

  it("reports the unsaved-change count after an edit", () => {
    const onDirtyCountChange = vi.fn();
    render(
      <MetadataForm
        fieldDefinitions={mockFieldDefs}
        values={defaultValues}
        onSave={vi.fn()}
        isSaving={false}
        onDirtyCountChange={onDirtyCountChange}
      />
    );

    const inputs = screen.getAllByRole("textbox");
    const titleInput = inputs.find(
      (i) => (i as HTMLInputElement).value === "Test Book Title"
    );
    if (titleInput) {
      fireEvent.change(titleInput, { target: { value: "New Title" } });
    }

    expect(onDirtyCountChange).toHaveBeenLastCalledWith(1);
  });

  it("saves the edited field through the registered action", () => {
    const onSave = vi.fn();
    const onRegisterActions = vi.fn();
    render(
      <MetadataForm
        fieldDefinitions={mockFieldDefs}
        values={defaultValues}
        onSave={onSave}
        isSaving={false}
        onRegisterActions={onRegisterActions}
      />
    );

    const inputs = screen.getAllByRole("textbox");
    const titleInput = inputs.find(
      (i) => (i as HTMLInputElement).value === "Test Book Title"
    );
    if (titleInput) {
      fireEvent.change(titleInput, { target: { value: "Modified Title" } });
    }

    onRegisterActions.mock.calls.at(-1)![0].save();

    expect(onSave).toHaveBeenCalled();
    const savedFields = onSave.mock.calls[0][0];
    expect(savedFields.title).toBe("Modified Title");
  });

  it("discards edits through the registered action", () => {
    const onDirtyCountChange = vi.fn();
    const onRegisterActions = vi.fn();
    render(
      <MetadataForm
        fieldDefinitions={mockFieldDefs}
        values={defaultValues}
        onSave={vi.fn()}
        isSaving={false}
        onDirtyCountChange={onDirtyCountChange}
        onRegisterActions={onRegisterActions}
      />
    );

    const inputs = screen.getAllByRole("textbox");
    const titleInput = inputs.find(
      (i) => (i as HTMLInputElement).value === "Test Book Title"
    );
    if (titleInput) {
      fireEvent.change(titleInput, { target: { value: "Ignored" } });
    }
    expect(onDirtyCountChange).toHaveBeenLastCalledWith(1);

    act(() => {
      onRegisterActions.mock.calls.at(-1)![0].discard();
    });

    expect(onDirtyCountChange).toHaveBeenLastCalledWith(0);
  });

  it("renders description as textarea (long text field)", () => {
    render(
      <MetadataForm
        fieldDefinitions={mockFieldDefs}
        values={defaultValues}
        onSave={vi.fn()}
        isSaving={false}
      />
    );
    const textareas = screen.getAllByRole("textbox").filter(
      (el) => el.tagName === "TEXTAREA"
    );
    expect(textareas.length).toBeGreaterThan(0);
  });

  it("renders add custom field button", () => {
    render(
      <MetadataForm
        fieldDefinitions={mockFieldDefs}
        values={defaultValues}
        onSave={vi.fn()}
        isSaving={false}
      />
    );
    expect(screen.getByText("Add")).toBeDefined();
  });

  it("disables add button when field name is empty", () => {
    render(
      <MetadataForm
        fieldDefinitions={mockFieldDefs}
        values={defaultValues}
        onSave={vi.fn()}
        isSaving={false}
      />
    );
    const addBtn = screen.getByText("Add").closest("button")!;
    expect(addBtn.disabled).toBe(true);
  });

  it("adds custom field on enter key", () => {
    render(
      <MetadataForm
        fieldDefinitions={mockFieldDefs}
        values={defaultValues}
        onSave={vi.fn()}
        isSaving={false}
      />
    );

    const nameInput = screen.getByPlaceholderText("e.g. printer");
    fireEvent.change(nameInput, { target: { value: "My Custom" } });
    fireEvent.keyDown(nameInput, { key: "Enter" });

    expect(screen.getByText("My Custom")).toBeDefined();
  });

  it("removes custom field on remove click", () => {
    render(
      <MetadataForm
        fieldDefinitions={mockFieldDefs}
        values={defaultValues}
        onSave={vi.fn()}
        isSaving={false}
      />
    );

    const nameInput = screen.getByPlaceholderText("e.g. printer");
    fireEvent.change(nameInput, { target: { value: "ToRemove" } });
    fireEvent.keyDown(nameInput, { key: "Enter" });

    expect(screen.getByText("ToRemove")).toBeDefined();

    fireEvent.click(screen.getByText(/^Remove$/));

    expect(screen.queryByText("ToRemove")).toBeNull();
  });
});
