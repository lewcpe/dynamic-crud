import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { vi, describe, it, expect, beforeEach } from "vitest"
import FieldManager from "./FieldManager"
import type { Field } from "../types"

const mockFields: Field[] = [
  { id: 1, table_id: 1, field_name: "name", field_type: "text", field_label: "Name", field_order: 0, created_at: "2024-01-01" },
  { id: 2, table_id: 1, field_name: "age", field_type: "int", field_label: "Age", field_order: 1, created_at: "2024-01-01" },
]

beforeEach(() => {
  vi.restoreAllMocks()
  vi.stubGlobal("fetch", vi.fn())
})

describe("FieldManager", () => {
  it("renders manage fields button with count", () => {
    render(<FieldManager tableId={1} fields={mockFields} onChange={() => {}} />)
    expect(screen.getByText(/Manage Fields/)).toBeInTheDocument()
  })

  it("adds a new field", async () => {
    const onChange = vi.fn()
    vi.mocked(fetch).mockResolvedValueOnce({ ok: true, json: async () => ({}) } as Response)
    render(<FieldManager tableId={1} fields={mockFields} onChange={onChange} />)

    await userEvent.click(screen.getByText(/Manage Fields/))
    await userEvent.type(screen.getByPlaceholderText(/status, priority/), "status")
    await userEvent.click(screen.getByText(/Add Field/))

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith("/api/tables/1/fields", expect.objectContaining({ method: "POST" }))
      expect(onChange).toHaveBeenCalled()
    })
  })

  it("deletes a field", async () => {
    vi.stubGlobal("confirm", () => true)
    vi.mocked(fetch).mockResolvedValueOnce({ ok: true, json: async () => ({}) } as Response)
    const onChange = vi.fn()
    render(<FieldManager tableId={1} fields={mockFields} onChange={onChange} />)

    await userEvent.click(screen.getByText(/Manage Fields/))
    const deleteButtons = screen.getAllByRole("button")
    const xButton = deleteButtons.find(b => b.querySelector("svg"))
    if (xButton) await userEvent.click(xButton)

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith("/api/tables/1/fields/1", expect.objectContaining({ method: "DELETE" }))
      expect(onChange).toHaveBeenCalled()
    })
  })
})
