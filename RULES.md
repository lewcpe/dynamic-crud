# PocketBase API Rules and Filters Specification

## 1. API Rules Overview
API Rules serve as collection access controls and data filters. Each collection contains up to five standard rules corresponding to specific API actions:
* `listRule`
* `viewRule`
* `createRule`
* `updateRule`
* `deleteRule`
* *Note:* Auth collections have an additional `options.manageRule` allowing a user to manage another user's data.

### Rule States
Each rule can be configured to one of the following states:
* **"locked" (null):** Default state. The action can only be performed by an authorized superuser.
* **Empty string (`""`):** Anyone (superusers, authorized users, and guests) can perform the action.
* **Non-empty string:** Only users satisfying the specified filter expression can perform the action. 

*Note: Rules act as record filters (e.g., `listRule` will only return items matching the filter). Superusers bypass all API rules.*

---

## 2. Filters Syntax

The syntax follows the format: `OPERAND OPERATOR OPERAND`

### Operands
Can be any field literal, string (single or double-quoted), number, `null`, `true`, or `false`.

### Field Groups
1.  **Collection Schema Fields:** Includes nested relation fields (e.g., `someRelField.status != "pending"`).
2.  **`@request.*` Fields:**
    * `@request.context` (e.g., `default`, `oauth2`, `otp`, `password`, `realtime`, `protectedFile`)
    * `@request.method` (e.g., `"GET"`)
    * `@request.headers.*` (Normalized to lowercase, `-` replaced with `_`)
    * `@request.query.*`
    * `@request.auth.*`
    * `@request.body.*` *(Note: Uploaded files are evaluated separately and not part of the body)*
3.  **`@collection.*` Fields:** Used to target other collections. You can define an alias by appending `:alias` to the collection name.

### Operators
* `=` (Equal) | `!=` (NOT equal)
* `>` (Greater than) | `>=` (Greater than or equal)
* `<` (Less than) | `<=` (Less than or equal)
* `~` (Like/Contains - auto-wraps right operand in `%`) | `!~` (NOT Like/Contains)

**"Any/At least one of" Operators** (Prefix with `?` for array-like values or multi-relations):
* `?=`, `?!=`, `?>`, `?>=`, `?<`, `?<=`, `?~`, `?!~`

### Grouping and Comments
* Use parenthesis `(...)`, `&&` (AND), and `||` (OR) to group expressions.
* Single line comments are supported using `//`.

---

## 3. Special Identifiers and Modifiers

### `@ macros` (UTC Based)
* **Time/Date Components:** `@second`, `@minute`, `@hour`, `@weekday`, `@day`, `@month`, `@year`
* **Relative/Exact Dates:** `@now`, `@yesterday`, `@tomorrow`, `@todayStart`, `@todayEnd`, `@monthStart`, `@monthEnd`, `@yearStart`, `@yearEnd`

### Field Modifiers
* `:isset` (For `@request.*`): Checks if specific data was submitted. Example: `@request.body.role:isset = false`
* `:changed` (For `@request.body.*`): Checks if data was both submitted and changed. Example: `@request.body.role:changed = false`
* `:length` (For arrays/relations): Checks item count. Example: `someRelationField:length = 2`
* `:each` (For arrays/relations): Applies a condition to every item. Example: `someSelectField:each ~ "pb_%"`
* `:lower` (String comparison): Performs lower-case evaluation. Example: `@request.body.title:lower = "test"`

### Special Functions
* **`geoDistance(lonA, latA, lonB, latB)`:** Calculates Haversine distance in kilometers.
    * *Example:* `geoDistance(address.lon, address.lat, 23.32, 42.69) < 25`
* **`strftime(format, [time-value, modifiers...])`:** Formats a date string similar to SQLite's `strftime`.
    * *Example:* `strftime('%Y-%m', multiRel.created) = "2026-01"`

---

## 4. Examples

* **Allow only registered users:**
    `@request.auth.id != ""`
* **Allow registered users and return "active" or "pending" records:**
    `@request.auth.id != "" && (status = "active" || status = "pending")`
* **Allow registered users listed in an `allowed_users` multi-relation:**
    `@request.auth.id != "" && allowed_users.id ?= @request.auth.id`
* **Allow public access but return only titles starting with "Lorem":**
    `title ~ "Lorem%"`
