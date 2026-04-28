import { render, screen, fireEvent } from "@testing-library/react"
import { vi, describe, it, expect } from "vitest"
import DataTable from "./DataTable"
import type { Field, Item } from "../types"

const fields: Field[] = [
  { id: 1, field_name: "name", field_type: "text", field_label: "Name", field_order: 0, created_at: "" },
]

const items: Item[] = [
  { id: 1, owner: "alice", created_at: "2024-01-01", updated_at: "2024-01-01", fields: { name: "Alice" } },
  { id: 2, owner: "bob", created_at: "2024-01-02", updated_at: "2024-01-02", fields: { name: "Bob" } },
]

describe("DataTable", () => {
  it("renders table columns from fields", () => {
    render(
      <DataTable
        fields={fields} items={[]} total={0} page={1} pageSize={20}
        search="" sortBy="id" sortDir="desc"
        onDataChange={() => {}} onSearchChange={() => {}}
        onPageChange={() => {}} onSortChange={() => {}}
      />
    )
    expect(screen.getByText("ID")).toBeInTheDocument()
    expect(screen.getByText("Owner")).toBeInTheDocument()
    expect(screen.getByText("Name")).toBeInTheDocument()
  })

  it("renders item rows", () => {
    render(
      <DataTable
        fields={fields} items={items} total={2} page={1} pageSize={20}
        search="" sortBy="id" sortDir="desc"
        onDataChange={() => {}} onSearchChange={() => {}}
        onPageChange={() => {}} onSortChange={() => {}}
      />
    )
    expect(screen.getByText("alice")).toBeInTheDocument()
    expect(screen.getByText("bob")).toBeInTheDocument()
    expect(screen.getByText("Alice")).toBeInTheDocument()
    expect(screen.getByText("Bob")).toBeInTheDocument()
  })

  it("calls search handler on input", async () => {
    const onSearch = vi.fn()
    render(
      <DataTable
        fields={fields} items={[]} total={0} page={1} pageSize={20}
        search="" sortBy="id" sortDir="desc"
        onDataChange={() => {}} onSearchChange={onSearch}
        onPageChange={() => {}} onSortChange={() => {}}
      />
    )
    fireEvent.change(screen.getByPlaceholderText("Search..."), { target: { value: "alice" } })
    expect(onSearch).toHaveBeenCalledWith("alice")
  })
})
