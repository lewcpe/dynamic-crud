import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { vi, describe, it, expect, beforeEach } from "vitest"
import ItemForm from "./ItemForm"
import type { Field } from "../types"

const fields: Field[] = [
  { id: 1, table_id: 1, field_name: "name", field_type: "text", field_label: "Name", field_order: 0, created_at: "" },
  { id: 2, table_id: 1, field_name: "age", field_type: "int", field_label: "Age", field_order: 1, created_at: "" },
]

beforeEach(() => {
  vi.restoreAllMocks()
  vi.stubGlobal("fetch", vi.fn())
})

describe("ItemForm", () => {
  it("renders form with dynamic fields", () => {
    render(<ItemForm open={true} onClose={() => {}} onSave={async () => {}} fields={fields} item={null} />)
    expect(screen.getByText("Create Item")).toBeInTheDocument()
    expect(screen.getByLabelText("Owner")).toBeInTheDocument()
    expect(screen.getByLabelText("Name")).toBeInTheDocument()
    expect(screen.getByLabelText("Age")).toBeInTheDocument()
  })

  it("submits create with field values", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined)
    render(<ItemForm open={true} onClose={() => {}} onSave={onSave} fields={fields} item={null} />)

    const ownerInput = screen.getByLabelText("Owner")
    await userEvent.clear(ownerInput)
    await userEvent.type(ownerInput, "alice")
    await userEvent.type(screen.getByLabelText("Name"), "Alice")
    await userEvent.type(screen.getByLabelText("Age"), "30")
    await userEvent.click(screen.getByText("Save"))

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith("alice", { name: "Alice", age: 30 })
    })
  })
})
