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
    expect(typeof actions.appendToField).toBe("function");
    // The form no longer owns a save button; the page's save bar does.
    expect(screen.queryByText(/Save metadata/)).toBeNull();
  });

  it("reports initial dirty, missing, and uncertain counts", () => {
    const onStatsChange = vi.fn();
    render(
      <MetadataForm
        fieldDefinitions={mockFieldDefs}
        values={defaultValues}
        onSave={vi.fn()}
        isSaving={false}
        onStatsChange={onStatsChange}
      />
    );
    expect(onStatsChange).toHaveBeenLastCalledWith({
      dirty: 0,
      missing: 2,
      uncertain: 1,
    });
  });

  it("reports the unsaved-change count after an edit", () => {
    const onStatsChange = vi.fn();
    render(
      <MetadataForm
        fieldDefinitions={mockFieldDefs}
        values={defaultValues}
        onSave={vi.fn()}
        isSaving={false}
        onStatsChange={onStatsChange}
      />
    );

    const inputs = screen.getAllByRole("textbox");
    const titleInput = inputs.find(
      (i) => (i as HTMLInputElement).value === "Test Book Title"
    );
    if (titleInput) {
      fireEvent.change(titleInput, { target: { value: "New Title" } });
    }

    expect(onStatsChange).toHaveBeenLastCalledWith({
      dirty: 1,
      missing: 2,
      uncertain: 1,
    });
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
    const onStatsChange = vi.fn();
    const onRegisterActions = vi.fn();
    render(
      <MetadataForm
        fieldDefinitions={mockFieldDefs}
        values={defaultValues}
        onSave={vi.fn()}
        isSaving={false}
        onStatsChange={onStatsChange}
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
    expect(onStatsChange).toHaveBeenLastCalledWith({
      dirty: 1,
      missing: 2,
      uncertain: 1,
    });

    act(() => {
      onRegisterActions.mock.calls.at(-1)![0].discard();
    });

    expect(onStatsChange).toHaveBeenLastCalledWith({
      dirty: 0,
      missing: 2,
      uncertain: 1,
    });
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

  it("filters rows to missing fields without losing the all view", () => {
    render(
      <MetadataForm
        fieldDefinitions={mockFieldDefs}
        values={defaultValues}
        onSave={vi.fn()}
        isSaving={false}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /^Missing \(2\)$/ }));
    expect(screen.getByLabelText("Publisher")).toBeDefined();
    expect(screen.getByLabelText("Description")).toBeDefined();
    expect(screen.queryByLabelText("Title")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: /^All \(5\)$/ }));
    expect(screen.getByLabelText("Title")).toBeDefined();
  });

  it("filters rows to uncertain fields", () => {
    render(
      <MetadataForm
        fieldDefinitions={mockFieldDefs}
        values={defaultValues}
        onSave={vi.fn()}
        isSaving={false}
      />
    );

    fireEvent.click(
      screen.getByRole("button", { name: /^Uncertain \(1\)$/ }),
    );
    expect(screen.getByLabelText("Publication Date")).toBeDefined();
    expect(screen.queryByLabelText("Publisher")).toBeNull();
  });

  it("keeps the focused row visible after it stops matching the filter", () => {
    render(
      <MetadataForm
        fieldDefinitions={mockFieldDefs}
        values={defaultValues}
        onSave={vi.fn()}
        isSaving={false}
      />
    );

    const publisher = screen.getByLabelText("Publisher");
    fireEvent.focus(publisher);
    fireEvent.click(screen.getByRole("button", { name: /^Missing \(2\)$/ }));
    fireEvent.change(publisher, { target: { value: "Now filled" } });

    expect(screen.getByLabelText("Publisher")).toBeDefined();
  });

  it("forces matched sections open while a filter is active", () => {
    const contributorDefs: MetadataFieldDefinition[] = [
      {
        field_name: "contributor",
        display_name: "Contributor",
        wikidata_property: null,
        batch_group: "contributors",
      },
    ];
    render(
      <MetadataForm
        fieldDefinitions={contributorDefs}
        values={{ contributor: "" }}
        onSave={vi.fn()}
        isSaving={false}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /^Missing \(1\)$/ }));
    expect(
      screen.getByRole("button", { name: /Contributors/ }).getAttribute(
        "aria-expanded",
      ),
    ).toBe("true");

    fireEvent.click(screen.getByRole("button", { name: /^All \(1\)$/ }));
    expect(
      screen.getByRole("button", { name: /Contributors/ }).getAttribute(
        "aria-expanded",
      ),
    ).toBe("false");
  });

  it("appends a passage through the registered action", () => {
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

    act(() => {
      onRegisterActions.mock.calls
        .at(-1)![0]
        .appendToField("title", "Additional wording");
    });

    expect((screen.getByLabelText("Title") as HTMLInputElement).value).toBe(
      "Test Book Title Additional wording",
    );
  });

  it("appends long-text passages with a newline and never overwrites", () => {
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

    act(() => {
      onRegisterActions.mock.calls
        .at(-1)![0]
        .appendToField("description_work", "First paragraph");
    });
    act(() => {
      onRegisterActions.mock.calls
        .at(-1)![0]
        .appendToField("description_work", "Second paragraph");
    });

    expect((screen.getByLabelText("Description") as HTMLTextAreaElement).value).toBe(
      "First paragraph\nSecond paragraph",
    );
  });

  it("shows a source page chip and reports the field", () => {
    const onShowSource = vi.fn();
    render(
      <MetadataForm
        fieldDefinitions={mockFieldDefs}
        values={defaultValues}
        onSave={vi.fn()}
        isSaving={false}
        onShowSource={onShowSource}
        confidenceByField={{
          publisher: {
            confidence: 0.9,
            extraction_method: "regex",
            source_page_number: 12,
            source_text_snippet: null,
          },
        }}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Source p.12" }));
    expect(onShowSource).toHaveBeenCalledWith("publisher");
  });

  it("steps to the next missing field", () => {
    const onFieldFocus = vi.fn();
    render(
      <MetadataForm
        fieldDefinitions={mockFieldDefs}
        values={defaultValues}
        onSave={vi.fn()}
        isSaving={false}
        onFieldFocus={onFieldFocus}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Next missing" }));
    expect(onFieldFocus).toHaveBeenCalledWith("publisher");
  });
});
