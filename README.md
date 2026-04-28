# Dynamic CRUD

A no-code application platform that lets users create data-driven applications without writing code. Define tables, fields, relationships, and permissions through a web UI.

## Features

- **Dynamic Tables** — Create tables and define fields (text, integer, float, date, datetime, file) at runtime
- **Relationships** — Link tables with one-to-one, one-to-many, or many-to-many relationships
- **Roles & Permissions** — Admin and user roles with table-level and row-level authorization using PocketBase-style rules
- **Groups** — Organize users into groups for permission management
- **File Attachments** — Upload files to any row
- **Comments** — Add comments on rows (requires write permission)
- **Search & Sort** — Full-text search and sorting across all fields and relationships

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12+, FastAPI, SQLite, Alembic |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Radix UI |
| Auth | JWT (python-jose), bcrypt |

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 18+
- [uv](https://docs.astral.sh/uv/) (Python package manager)

### 1. Clone the repository

```bash
git clone git@github.com:lewcpe/dynamic-crud.git
cd dynamic-crud
```

### 2. Start the backend

```bash
cd backend
uv sync                  # Install dependencies
uv run uvicorn main:app --reload --port 8000
```

The backend runs at `http://localhost:8000`. On first startup it automatically:
- Creates the SQLite database (`data.db`)
- Runs all Alembic migrations

### 3. Start the frontend

In a new terminal:

```bash
cd frontend
npm install              # Install dependencies
npm run dev              # Start dev server
```

The frontend runs at `http://localhost:5173` and proxies API requests to the backend.

### 4. Register your first user

Open `http://localhost:5173` and register. The **first user** automatically becomes an admin.

## Production Build

Build the frontend into the backend's static directory:

```bash
cd frontend
npm run build
```

Then serve everything from the backend:

```bash
cd backend
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

The app is available at `http://localhost:8000`.

## Usage Guide

### As an Admin

1. **Create a table** — Click "Tables" in the header, enter a name and label
2. **Add fields** — Click "Fields", add columns with types (text, int, float, date, datetime)
3. **Add relationships** — Click "Relationships" to link tables (1-1, 1-n, n-n)
4. **Set permissions** — Click "Permissions" to control access per table
5. **Manage users** — Click "Users" to promote/demote admins or delete users
6. **Manage groups** — Click "Groups" to create groups and assign members

### As a User

1. **Browse tables** — Use the table selector dropdown
2. **Create items** — Click "+ New Item" and fill in the fields
3. **Edit/Delete** — Use the pencil/trash icons on each row
4. **Search** — Type in the search box to filter across all columns
5. **Sort** — Click any column header to sort ascending/descending

### Permission Rules

Permissions use PocketBase-style expressions:

| Rule | Meaning |
|------|---------|
| *(empty)* | Open — anyone can perform the action |
| *(null/locked)* | Locked — only admins can perform the action |
| `@request.auth.id != ""` | Any authenticated user |
| `status = "published"` | Only rows where status is "published" |
| `owner = "alice"` | Only rows where owner equals "alice" |
| `status = "active" && owner = "me"` | Compound conditions with AND |
| `status = "draft" \|\| status = "review"` | Compound conditions with OR |
| `price > 100` | Numeric comparisons |
| `name ~ "John"` | Partial string matching (LIKE) |

## Project Structure

```
dynamic-crud/
├── backend/
│   ├── main.py              # FastAPI application (all routes and logic)
│   ├── alembic/             # Database migrations
│   │   └── versions/
│   ├── static/              # Built frontend (served by FastAPI)
│   ├── test_*.py            # Backend tests
│   ├── pyproject.toml       # Python dependencies
│   └── data.db              # SQLite database (created at runtime)
├── frontend/
│   ├── src/
│   │   ├── api.ts           # API client
│   │   ├── types.ts         # TypeScript interfaces
│   │   ├── App.tsx          # Main React component
│   │   └── components/      # UI components
│   ├── package.json         # Node dependencies
│   └── vite.config.ts       # Vite config (proxy + build output)
├── GOALS.md                 # Feature requirements
└── RULES.md                 # PocketBase rule syntax reference
```

## API Endpoints

### Auth
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/register` | Register a new user |
| POST | `/api/auth/login` | Login and get JWT token |
| GET | `/api/auth/me` | Get current user info |

### Tables
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/tables` | List all tables |
| POST | `/api/tables` | Create a table |
| PUT | `/api/tables/{id}` | Update a table |
| DELETE | `/api/tables/{id}` | Delete a table |

### Fields
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/tables/{id}/fields` | List fields |
| POST | `/api/tables/{id}/fields` | Create a field |
| PUT | `/api/tables/{id}/fields/{fid}` | Update a field |
| DELETE | `/api/tables/{id}/fields/{fid}` | Delete a field |

### Items
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/tables/{id}/items` | List items (paginated, searchable) |
| GET | `/api/tables/{id}/items/{iid}` | Get an item |
| POST | `/api/tables/{id}/items` | Create an item |
| PUT | `/api/tables/{id}/items/{iid}` | Update an item |
| DELETE | `/api/tables/{id}/items/{iid}` | Delete an item |

### Relationships
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/tables/{id}/relationships` | List relationships |
| POST | `/api/tables/{id}/relationships` | Create a relationship |
| POST | `/api/tables/{id}/relationships/{rid}/link` | Set relationship links |

### Permissions
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/tables/{id}/permissions` | List permissions (admin) |
| POST | `/api/tables/{id}/permissions` | Create permission (admin) |
| DELETE | `/api/tables/{id}/permissions/{pid}` | Delete permission (admin) |

### Files & Comments
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/tables/{id}/items/{iid}/files` | Upload file |
| GET | `/api/tables/{id}/items/{iid}/files` | List files |
| GET | `/api/files/{fid}` | Download file |
| GET | `/api/tables/{id}/items/{iid}/comments` | List comments |
| POST | `/api/tables/{id}/items/{iid}/comments` | Add comment |

## Running Tests

```bash
# Backend tests (82 tests)
cd backend
uv run pytest -v

# Frontend tests (8 tests)
cd frontend
npm test
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | `dev-secret-change-in-production` | JWT signing key |

## License

MIT
