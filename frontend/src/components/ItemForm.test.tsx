import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { vi, describe, it, expect, beforeEach } from "vitest"
import ItemForm from "./ItemForm"
import type { Field, User } from "../types"

const fields: Field[] = [
  { id: 1, table_id: 1, field_name: "name", field_type: "text", field_label: "Name", field_order: 0, created_at: "" },
  { id: 2, table_id: 1, field_name: "age", field_type: "int", field_label: "Age", field_order: 1, created_at: "" },
]

const adminUser: User = { id: 1, email: "admin@test.com", name: "Admin", role: "admin", manager_id: null, created_at: "" }
const regularUser: User = { id: 2, email: "user@test.com", name: "User", role: "user", manager_id: null, created_at: "" }

beforeEach(() => {
  vi.restoreAllMocks()
  vi.stubGlobal("fetch", vi.fn())
})

describe("ItemForm", () => {
  it("renders form with dynamic fields", () => {
    render(<ItemForm open={true} onClose={() => {}} onSave={async () => ({ id: 1, owner: "", created_at: "", updated_at: "", fields: {} })} onSaved={() => {}} tableId={1} fields={fields} relationships={[]} user={regularUser} item={null} />)
    expect(screen.getByText("Create Item")).toBeInTheDocument()
    expect(screen.getByLabelText("Owner")).toBeInTheDocument()
    expect(screen.getByLabelText("Name")).toBeInTheDocument()
    expect(screen.getByLabelText("Age")).toBeInTheDocument()
  })

  it("defaults owner to current user name", () => {
    render(<ItemForm open={true} onClose={() => {}} onSave={async () => ({ id: 1, owner: "", created_at: "", updated_at: "", fields: {} })} onSaved={() => {}} tableId={1} fields={fields} relationships={[]} user={regularUser} item={null} />)
    expect(screen.getByLabelText("Owner")).toHaveValue("User")
  })

  it("submits create with field values", async () => {
    const onSave = vi.fn().mockResolvedValue({ id: 1, owner: "", created_at: "", updated_at: "", fields: {} })
    const onSaved = vi.fn()
    render(<ItemForm open={true} onClose={() => {}} onSave={onSave} onSaved={onSaved} tableId={1} fields={fields} relationships={[]} user={regularUser} item={null} />)

    await userEvent.type(screen.getByLabelText("Name"), "Alice")
    await userEvent.type(screen.getByLabelText("Age"), "30")
    await userEvent.click(screen.getByText("Save"))

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith("User", { name: "Alice", age: 30 })
      expect(onSaved).toHaveBeenCalled()
    })
  })
})
