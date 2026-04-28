import json
import re
from .database import get_fields, get_relationships, get_items_table


def item_row_to_dict(row, fields: list[dict]) -> dict:
    item = dict(row)
    item.pop("data", None)
    json_data = {}
    try:
        json_data = json.loads(row["data"] or "{}")
    except json.JSONDecodeError:
        pass
    for f in fields:
        name = f["field_name"]
        if name not in json_data:
            json_data[name] = row[name] if name in row.keys() else None
    item["fields"] = json_data
    return item


def get_default_represent(conn, table_id: int) -> str:
    row = conn.execute(
        "SELECT field_name FROM dynamic_fields WHERE table_id = ? AND field_type = 'text' ORDER BY field_order, id LIMIT 1",
        (table_id,),
    ).fetchone()
    if row:
        return "{" + row["field_name"] + "}"
    return "{id}"


def format_represent(represent: str, item: dict) -> str:
    # Build case-insensitive lookup for fields
    fields = item.get("fields", {})
    lower_fields = {k.lower(): v for k, v in fields.items()}

    def replacer(m):
        key = m.group(1)
        # Try exact match first, then case-insensitive
        val = fields.get(key)
        if val is None:
            val = lower_fields.get(key.lower())
        if val is None:
            val = item.get(key)
        return str(val) if val is not None else ""
    return re.sub(r"\{([^}]+)\}", replacer, represent)


def get_item_label(conn, table_id: int, item_id: int) -> str:
    table = get_items_table(table_id)
    row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (item_id,)).fetchone()
    if not row:
        return str(item_id)

    table_info = conn.execute("SELECT represent FROM dynamic_tables WHERE id = ?", (table_id,)).fetchone()
    represent = table_info["represent"] if table_info and table_info["represent"] else ""

    if represent:
        fields = get_fields(conn, table_id)
        item = item_row_to_dict(row, fields)
        result = format_represent(represent, item)
        if result.strip():
            return result

    owner = row["owner"] if "owner" in row.keys() else None
    return owner or str(item_id)


def get_system_item_label(conn, system_table: str, item_id: int) -> str:
    if system_table == "users":
        row = conn.execute("SELECT name, email FROM users WHERE id = ?", (item_id,)).fetchone()
        if row:
            return row["name"] or row["email"] or str(item_id)
    elif system_table == "groups":
        row = conn.execute("SELECT name FROM groups WHERE id = ?", (item_id,)).fetchone()
        if row:
            return row["name"] or str(item_id)
    return str(item_id)


def enrich_item_with_relationships(conn, table_id: int, item: dict) -> dict:
    rels = get_relationships(conn, table_id)
    relationships = {}
    for rel in rels:
        rel_id = rel["id"]
        rel_name = rel["rel_name"]
        rel_type = rel["rel_type"]
        is_from = rel["from_table_id"] == table_id
        to_system = rel.get("to_system_table")

        if rel_type in ("1-1", "1-n"):
            if is_from:
                col = f"rel_{rel_id}"
                fk_val = item["fields"].get(col) or item.get(col)
                if fk_val is not None:
                    if to_system:
                        label = get_system_item_label(conn, to_system, fk_val)
                    else:
                        label = get_item_label(conn, rel["to_table_id"], fk_val)
                else:
                    fk_val = None
                    label = None
                relationships[rel_name] = {
                    "rel_id": rel_id,
                    "rel_type": rel_type,
                    "direction": "from",
                    "table_id": rel["to_table_id"],
                    "system_table": to_system,
                    "item_id": fk_val,
                    "label": label,
                }
            else:
                if to_system:
                    continue
                other_table = rel["from_table_id"]
                other_items = get_items_table(other_table)
                col = f"rel_{rel_id}"
                rows = conn.execute(
                    f"SELECT id FROM {other_items} WHERE {col} = ?",
                    (item["id"],),
                ).fetchall()
                items_list = []
                for r in rows:
                    label = get_item_label(conn, other_table, r["id"])
                    items_list.append({"item_id": r["id"], "label": label})
                relationships[rel_name] = {
                    "rel_id": rel_id,
                    "rel_type": rel_type,
                    "direction": "to",
                    "table_id": other_table,
                    "items": items_list,
                }
        elif rel_type == "n-n":
            junction = f"rel_{rel_id}"
            if is_from:
                rows = conn.execute(
                    f"SELECT to_item_id FROM {junction} WHERE from_item_id = ?",
                    (item["id"],),
                ).fetchall()
                items_list = []
                for r in rows:
                    tid = r["to_item_id"]
                    if to_system:
                        label = get_system_item_label(conn, to_system, tid)
                    else:
                        label = get_item_label(conn, rel["to_table_id"], tid)
                    items_list.append({"item_id": tid, "label": label})
                relationships[rel_name] = {
                    "rel_id": rel_id,
                    "rel_type": rel_type,
                    "direction": "from",
                    "table_id": rel["to_table_id"],
                    "system_table": to_system,
                    "items": items_list,
                }
            else:
                if to_system:
                    continue
                other_table = rel["from_table_id"]
                rows = conn.execute(
                    f"SELECT from_item_id FROM {junction} WHERE to_item_id = ?",
                    (item["id"],),
                ).fetchall()
                items_list = []
                for r in rows:
                    fid = r["from_item_id"]
                    label = get_item_label(conn, other_table, fid)
                    items_list.append({"item_id": fid, "label": label})
                relationships[rel_name] = {
                    "rel_id": rel_id,
                    "rel_type": rel_type,
                    "direction": "to",
                    "table_id": other_table,
                    "items": items_list,
                }
    item["relationships"] = relationships
    return item
