import sqlite3
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Depends, UploadFile, File as FastAPIFile, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, model_validator
from passlib.context import CryptContext
from jose import jwt, JWTError
import bcrypt

DB_PATH = Path(__file__).parent / "data.db"
STATIC_DIR = Path(__file__).parent / "static"
FIELD_TYPES = ["int", "float", "text", "date", "datetime", "file", "files"]
REL_TYPES = ["1-1", "1-n", "n-n"]
RESERVED_FIELD_NAMES = ("id", "owner", "created_at", "updated_at", "data")

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def get_items_table(table_id: int) -> str:
    return f"items_{table_id}"


def run_migrations():
    from alembic.config import Config
    from alembic import command

    alembic_cfg = Config()
    alembic_cfg.set_main_option(
        "script_location", str(Path(__file__).parent / "alembic")
    )
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{DB_PATH}")
    command.upgrade(alembic_cfg, "head")


def get_fields(conn: sqlite3.Connection, table_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM dynamic_fields WHERE table_id = ? ORDER BY field_order, id",
        (table_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_relationships(conn: sqlite3.Connection, table_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM dynamic_relationships WHERE from_table_id = ? OR to_table_id = ?",
        (table_id, table_id),
    ).fetchall()
    return [dict(r) for r in rows]


def get_relationships_from(conn: sqlite3.Connection, table_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM dynamic_relationships WHERE from_table_id = ?",
        (table_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def validate_item_data(fields: list[dict], data: dict) -> dict:
    validated = {}
    for f in fields:
        name = f["field_name"]
        ftype = f["field_type"]
        raw = data.get(name)
        if raw is None or raw == "":
            validated[name] = None
            continue
        if ftype == "int":
            try:
                validated[name] = int(raw)
            except (ValueError, TypeError):
                raise HTTPException(400, f"Field '{name}' must be an integer")
        elif ftype == "float":
            try:
                validated[name] = float(raw)
            except (ValueError, TypeError):
                raise HTTPException(400, f"Field '{name}' must be a float")
        elif ftype in ("text", "date", "datetime"):
            validated[name] = str(raw)
        else:
            validated[name] = str(raw)
    return validated


def alter_table_for_new_field(
    conn: sqlite3.Connection, table_id: int, field_name: str, field_type: str
):
    table = get_items_table(table_id)
    sqlite_type = "TEXT"
    if field_type == "int":
        sqlite_type = "INTEGER"
    elif field_type == "float":
        sqlite_type = "REAL"
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {field_name} {sqlite_type}")
    except sqlite3.OperationalError:
        pass


def drop_column_from_table(
    conn: sqlite3.Connection, table_id: int, field_name: str
):
    table = get_items_table(table_id)
    try:
        conn.execute(f"ALTER TABLE {table} DROP COLUMN {field_name}")
    except sqlite3.OperationalError:
        cols = [
            r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()
        ]
        if field_name not in cols:
            return
        cols.remove(field_name)
        quoted = ", ".join(cols)
        conn.execute(
            f"CREATE TABLE {table}_new AS SELECT {quoted} FROM {table}"
        )
        conn.execute(f"DROP TABLE {table}")
        conn.execute(f"ALTER TABLE {table}_new RENAME TO {table}")


def item_row_to_dict(row: sqlite3.Row, fields: list[dict]) -> dict:
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


def get_item_label(conn: sqlite3.Connection, table_id: int, item_id: int) -> str:
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


# ── Auth helpers ──────────────────────────────────────────────────────────────

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


def get_user_by_id(conn: sqlite3.Connection, user_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def get_user_by_email(conn: sqlite3.Connection, email: str) -> dict | None:
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    return dict(row) if row else None


def get_user_groups(conn: sqlite3.Connection, user_id: int) -> list[int]:
    rows = conn.execute(
        "SELECT group_id FROM user_groups WHERE user_id = ?", (user_id,)
    ).fetchall()
    return [r["group_id"] for r in rows]


def get_current_user_optional(request: Request) -> dict | None:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:]
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        return None
    conn = get_db()
    user = get_user_by_id(conn, int(payload["sub"]))
    conn.close()
    return user


def get_current_user(request: Request) -> dict:
    user = get_current_user_optional(request)
    if not user:
        raise HTTPException(401, "Not authenticated")
    return user


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(403, "Admin access required")
    return user


def check_table_permission(
    conn: sqlite3.Connection,
    table_id: int,
    action: str,
    user: dict | None,
    item: dict | None = None,
) -> bool:
    if user and user["role"] == "admin":
        return True

    perms = conn.execute(
        "SELECT * FROM permissions WHERE table_id = ?", (table_id,)
    ).fetchall()

    if not perms:
        return True

    matched = False
    for perm in perms:
        if not _permission_applies(perm, user):
            continue
        matched = True
        rule = perm[f"{action}_rule"]
        if rule is None:
            return False
        if rule == "":
            return True
        if action == "list":
            return True
        if item and table_id:
            try:
                parser = RuleParser(rule, user, table_id, conn)
                if parser.evaluate_for_item(item):
                    return True
            except Exception:
                continue
        elif not item:
            return True

    if not matched:
        return True
    return False


def _permission_applies(perm: dict, user: dict | None) -> bool:
    target_type = perm["target_type"]
    if target_type == "role":
        target_role = perm["target_role"]
        if target_role == "user":
            return user is not None
        if target_role == "guest":
            return user is None
        return False
    if target_type == "user":
        if not user:
            return False
        return perm["target_id"] == user["id"]
    if target_type == "group":
        if not user:
            return False
        groups = get_user_groups_sqlite(user["id"])
        return perm["target_id"] in groups
    return False


def get_user_groups_sqlite(user_id: int) -> list[int]:
    conn = get_db()
    rows = conn.execute(
        "SELECT group_id FROM user_groups WHERE user_id = ?", (user_id,)
    ).fetchall()
    conn.close()
    return [r["group_id"] for r in rows]


def evaluate_rule(
    rule: str,
    user: dict | None,
    item: dict | None,
    conn: sqlite3.Connection,
    table_id: int = 0,
) -> bool:
    if not rule or not rule.strip():
        return True

    rule = rule.strip()

    if rule == "@request.auth.id != \"\"":
        return user is not None

    if rule.startswith("@request.auth.id"):
        if "!=" in rule:
            return user is not None
        if "=" in rule and "!=" not in rule:
            return user is not None

    if ".id ?= @request.auth.id" in rule:
        if not user or not item:
            return False
        field_part = rule.split(".id ?=")[0].strip()
        rel_val = item.get("relationships", {}).get(field_part)
        if not rel_val:
            return False
        if "items" in rel_val:
            return any(i["item_id"] == user["id"] for i in rel_val["items"])
        if "item_id" in rel_val:
            return rel_val["item_id"] == user["id"]
        return False

    if item and table_id:
        try:
            parser = RuleParser(rule, user, table_id, conn)
            return parser.evaluate_for_item(item)
        except Exception:
            return False

    return False


import re
import operator


class RuleParser:
    TOKEN_PATTERN = re.compile(
        r'"[^"]*"'
        r"|'[^']*'"
        r"|@request\.auth\.\w+"
        r"|@now|@todayStart|@todayEnd|@yesterday|@tomorrow"
        r"|@yearStart|@yearEnd|@monthStart|@monthEnd"
        r"|\?\=|\?\!=|\?~|\?!~"
        r"|\>=|\<=|\!=|~|!~"
        r"|=|>|<"
        r"|\&\&|\|\|"
        r"|\(|\)"
        r"|\d+\.?\d*"
        r"|[a-zA-Z_][a-zA-Z0-9_.]*"
        r"|\s+"
    )

    def __init__(self, rule: str, user: dict | None, table_id: int, conn: sqlite3.Connection):
        self.rule = rule
        self.user = user
        self.table_id = table_id
        self.conn = conn
        self.tokens = self._tokenize(rule)
        self.pos = 0

    def _tokenize(self, rule: str) -> list[str]:
        raw = self.TOKEN_PATTERN.findall(rule)
        return [t for t in raw if not t.isspace()]

    def peek(self) -> str | None:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def consume(self) -> str:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def expect(self, expected: str):
        tok = self.consume()
        if tok != expected:
            raise ValueError(f"Expected '{expected}', got '{tok}'")

    def parse(self):
        return self._parse_or()

    def _parse_or(self):
        left = self._parse_and()
        while self.peek() == "||":
            self.consume()
            right = self._parse_and()
            left = ("or", left, right)
        return left

    def _parse_and(self):
        left = self._parse_not()
        while self.peek() == "&&":
            self.consume()
            right = self._parse_not()
            left = ("and", left, right)
        return left

    def _parse_not(self):
        if self.peek() == "!":
            self.consume()
            expr = self._parse_primary()
            return ("not", expr)
        return self._parse_primary()

    def _parse_primary(self):
        tok = self.peek()
        if tok == "(":
            self.consume()
            expr = self._parse_or()
            self.expect(")")
            return expr
        return self._parse_comparison()

    def _parse_comparison(self):
        left = self._parse_value()
        op = self.peek()
        if op in ("=", "!=", ">", ">=", "<", "<=", "~", "!~",
                   "?=", "?!=", "?~", "?!~"):
            self.consume()
            right = self._parse_value()
            return ("cmp", op, left, right)
        return left

    def _parse_value(self):
        tok = self.peek()
        if tok is None:
            raise ValueError("Unexpected end of rule")

        if tok.startswith("@request.auth."):
            self.consume()
            return ("auth", tok.split(".")[-1])

        if tok.startswith("@"):
            self.consume()
            return ("macro", tok)

        if tok.startswith('"') or tok.startswith("'"):
            self.consume()
            return ("literal", tok[1:-1])

        if tok.replace(".", "", 1).isdigit():
            self.consume()
            if "." in tok:
                return ("literal", float(tok))
            return ("literal", int(tok))

        if tok == "true":
            self.consume()
            return ("literal", True)
        if tok == "false":
            self.consume()
            return ("literal", False)
        if tok == "null":
            self.consume()
            return ("literal", None)

        self.consume()
        if "." in tok:
            parts = tok.split(".", 1)
            return ("field_rel", parts[0], parts[1])
        return ("field", tok)

    def to_sql_where(self, params: list) -> str:
        ast = self.parse()
        return self._ast_to_sql(ast, params)

    def _ast_to_sql(self, node, params: list) -> str:
        if node[0] == "or":
            left = self._ast_to_sql(node[1], params)
            right = self._ast_to_sql(node[2], params)
            return f"({left} OR {right})"
        if node[0] == "and":
            left = self._ast_to_sql(node[1], params)
            right = self._ast_to_sql(node[2], params)
            return f"({left} AND {right})"
        if node[0] == "not":
            expr = self._ast_to_sql(node[1], params)
            return f"(NOT {expr})"
        if node[0] == "cmp":
            op = node[1]
            left_sql = self._ast_to_sql(node[2], params)
            right_sql = self._ast_to_sql(node[3], params)
            sql_op = self._op_to_sql(op)
            return f"({left_sql} {sql_op} {right_sql})"
        if node[0] == "auth":
            field = node[1]
            if self.user:
                params.append(self.user.get(field))
            else:
                params.append(None)
            return "?"
        if node[0] == "macro":
            return self._macro_to_sql(node[1])
        if node[0] == "literal":
            params.append(node[1])
            return "?"
        if node[0] == "field":
            return node[1]
        if node[0] == "field_rel":
            rel_name = node[1]
            rel_field = node[2]
            return self._relationship_to_sql(rel_name, rel_field, params)
        raise ValueError(f"Unknown node type: {node[0]}")

    def _op_to_sql(self, op: str) -> str:
        mapping = {
            "=": "=", "!=": "!=", ">": ">", ">=": ">=",
            "<": "<", "<=": "<=", "~": "LIKE", "!~": "NOT LIKE",
            "?=": "=", "?!=": "!=", "?~": "LIKE", "?!~": "NOT LIKE",
        }
        return mapping.get(op, op)

    def _macro_to_sql(self, macro: str) -> str:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        if macro == "@now":
            return f"'{now.strftime('%Y-%m-%d %H:%M:%S')}'"
        if macro == "@todayStart":
            return f"'{now.strftime('%Y-%m-%d')} 00:00:00'"
        if macro == "@todayEnd":
            return f"'{now.strftime('%Y-%m-%d')} 23:59:59'"
        return "NULL"

    def _relationship_to_sql(self, rel_name: str, rel_field: str, params: list) -> str:
        rels = get_relationships_from(self.conn, self.table_id)
        rel = next((r for r in rels if r["rel_name"] == rel_name), None)
        if not rel:
            params.append(None)
            return "?"

        rel_type = rel["rel_type"]
        rel_id = rel["id"]

        if rel_type in ("1-1", "1-n"):
            col = f"rel_{rel_id}"
            return col
        return "NULL"

    def evaluate_for_item(self, item: dict) -> bool:
        ast = self.parse()
        return self._eval_ast(ast, item)

    def _eval_ast(self, node, item: dict) -> bool:
        if node[0] == "or":
            return self._eval_ast(node[1], item) or self._eval_ast(node[2], item)
        if node[0] == "and":
            return self._eval_ast(node[1], item) and self._eval_ast(node[2], item)
        if node[0] == "not":
            return not self._eval_ast(node[1], item)
        if node[0] == "cmp":
            op = node[1]
            left_val = self._eval_value(node[2], item)
            right_val = self._eval_value(node[3], item)
            return self._compare(op, left_val, right_val)
        if node[0] in ("auth", "macro", "literal", "field", "field_rel"):
            return bool(self._eval_value(node, item))
        return False

    def _eval_value(self, node, item: dict):
        if node[0] == "auth":
            if not self.user:
                return None
            return self.user.get(node[1])
        if node[0] == "literal":
            return node[1]
        if node[0] == "field":
            return item.get("fields", {}).get(node[1])
        if node[0] == "field_rel":
            rel_name = node[1]
            rels = item.get("relationships", {})
            rel_val = rels.get(rel_name)
            if not rel_val:
                return None
            if "item_id" in rel_val:
                return rel_val["item_id"]
            if "items" in rel_val:
                return [i["item_id"] for i in rel_val["items"]]
            return None
        if node[0] == "macro":
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            if node[1] == "@now":
                return now.strftime("%Y-%m-%d %H:%M:%S")
            return None
        return None

    def _compare(self, op: str, left, right) -> bool:
        if left is None and right is None:
            return op in ("=", "?=")
        if left is None or right is None:
            return op in ("!=", "?!=")

        if op in ("?=", "?!="):
            if isinstance(left, list):
                if op == "?=":
                    return right in left
                return right not in left
            return self._compare(op[1:], left, right)

        if op == "=":
            return left == right
        if op == "!=":
            return left != right
        if op == ">":
            return left > right
        if op == ">=":
            return left >= right
        if op == "<":
            return left < right
        if op == "<=":
            return left <= right
        if op == "~":
            return str(right).replace("%", "") in str(left)
        if op == "!~":
            return str(right).replace("%", "") not in str(left)
        return False


def get_row_level_filter(
    conn: sqlite3.Connection,
    table_id: int,
    action: str,
    user: dict | None,
    params: list,
) -> str | None:
    if user and user["role"] == "admin":
        return None

    perms = conn.execute(
        "SELECT * FROM permissions WHERE table_id = ?", (table_id,)
    ).fetchall()

    if not perms:
        return None

    for perm in perms:
        if not _permission_applies(perm, user):
            continue
        rule = perm[f"{action}_rule"]
        if rule is None:
            return "1=0"
        if rule == "":
            return None
        try:
            parser = RuleParser(rule, user, table_id, conn)
            return parser.to_sql_where(params)
        except Exception:
            continue

    return "1=0"


def get_user_permissions(
    conn: sqlite3.Connection, table_id: int, user: dict | None
) -> dict:
    actions = ["list", "view", "create", "update", "delete"]
    result = {}
    for action in actions:
        result[action] = check_table_permission(conn, table_id, action, user)
    return result


# ── Enrich items ──────────────────────────────────────────────────────────────

def get_system_item_label(conn: sqlite3.Connection, system_table: str, item_id: int) -> str:
    if system_table == "users":
        row = conn.execute("SELECT name, email FROM users WHERE id = ?", (item_id,)).fetchone()
        if row:
            return row["name"] or row["email"] or str(item_id)
    elif system_table == "groups":
        row = conn.execute("SELECT name FROM groups WHERE id = ?", (item_id,)).fetchone()
        if row:
            return row["name"] or str(item_id)
    return str(item_id)


def enrich_item_with_relationships(
    conn: sqlite3.Connection, table_id: int, item: dict
) -> dict:
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
                    f"SELECT id, owner FROM {other_items} WHERE {col} = ?",
                    (item["id"],),
                ).fetchall()
                relationships[rel_name] = {
                    "rel_id": rel_id,
                    "rel_type": rel_type,
                    "direction": "to",
                    "table_id": other_table,
                    "items": [
                        {"item_id": r["id"], "label": r["owner"] or str(r["id"])}
                        for r in rows
                    ],
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    yield


app = FastAPI(title="Dynamic CRUD", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Table management ──────────────────────────────────────────────────────────

class TableCreate(BaseModel):
    name: str
    label: str = ""
    represent: str = ""


class TableUpdate(BaseModel):
    name: str | None = None
    label: str | None = None
    represent: str | None = None


def get_default_represent(conn: sqlite3.Connection, table_id: int) -> str:
    row = conn.execute(
        "SELECT field_name FROM dynamic_fields WHERE table_id = ? AND field_type = 'text' ORDER BY field_order, id LIMIT 1",
        (table_id,),
    ).fetchone()
    if row:
        return "{" + row["field_name"] + "}"
    return "{id}"


def format_represent(represent: str, item: dict) -> str:
    import re
    def replacer(m):
        key = m.group(1)
        val = item.get("fields", {}).get(key)
        if val is None:
            val = item.get(key, "")
        return str(val) if val is not None else ""
    return re.sub(r"\{([^}]+)\}", replacer, represent)


@app.get("/api/tables")
def list_tables():
    conn = get_db()
    rows = conn.execute("SELECT * FROM dynamic_tables ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/api/tables", status_code=201)
def create_table(payload: TableCreate):
    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM dynamic_tables WHERE name = ?", (payload.name,)
    ).fetchone()
    if existing:
        conn.close()
        raise HTTPException(400, f"Table '{payload.name}' already exists")

    conn.execute(
        "INSERT INTO dynamic_tables (name, label, represent) VALUES (?, ?, ?)",
        (payload.name, payload.label or payload.name, payload.represent),
    )
    table_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    conn.execute(f"""
        CREATE TABLE {get_items_table(table_id)} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner TEXT NOT NULL DEFAULT 'default',
            data TEXT NOT NULL DEFAULT '{{}}',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    row = conn.execute(
        "SELECT * FROM dynamic_tables WHERE id = ?", (table_id,)
    ).fetchone()
    conn.close()
    return dict(row)


@app.put("/api/tables/{table_id}")
def update_table(table_id: int, payload: TableUpdate):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM dynamic_tables WHERE id = ?", (table_id,)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Table not found")
    if payload.name is not None:
        conn.execute(
            "UPDATE dynamic_tables SET name = ? WHERE id = ?",
            (payload.name, table_id),
        )
    if payload.label is not None:
        conn.execute(
            "UPDATE dynamic_tables SET label = ? WHERE id = ?",
            (payload.label, table_id),
        )
    if payload.represent is not None:
        conn.execute(
            "UPDATE dynamic_tables SET represent = ? WHERE id = ?",
            (payload.represent, table_id),
        )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM dynamic_tables WHERE id = ?", (table_id,)
    ).fetchone()
    conn.close()
    return dict(row)


@app.delete("/api/tables/{table_id}")
def delete_table(table_id: int):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM dynamic_tables WHERE id = ?", (table_id,)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Table not found")

    rels = get_relationships(conn, table_id)
    for rel in rels:
        _drop_relationship_storage(conn, rel)

    conn.execute("DELETE FROM dynamic_relationships WHERE from_table_id = ? OR to_table_id = ?",
                 (table_id, table_id))
    conn.execute("DELETE FROM dynamic_fields WHERE table_id = ?", (table_id,))
    conn.execute(f"DROP TABLE IF EXISTS {get_items_table(table_id)}")
    conn.execute("DELETE FROM dynamic_tables WHERE id = ?", (table_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


# ── Field management ──────────────────────────────────────────────────────────

class FieldCreate(BaseModel):
    field_name: str
    field_type: str
    field_label: str = ""

    @model_validator(mode="after")
    def check_type(self):
        if self.field_type not in FIELD_TYPES:
            raise ValueError(f"field_type must be one of {FIELD_TYPES}")
        return self


class FieldUpdate(BaseModel):
    field_label: str | None = None
    field_type: str | None = None

    @model_validator(mode="after")
    def check_type(self):
        if self.field_type is not None and self.field_type not in FIELD_TYPES:
            raise ValueError(f"field_type must be one of {FIELD_TYPES}")
        return self


def _ensure_table_exists(conn: sqlite3.Connection, table_id: int):
    row = conn.execute(
        "SELECT id FROM dynamic_tables WHERE id = ?", (table_id,)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Table not found")
    return row


@app.get("/api/tables/{table_id}/fields")
def list_fields(table_id: int):
    conn = get_db()
    _ensure_table_exists(conn, table_id)
    fields = get_fields(conn, table_id)
    conn.close()
    return fields


@app.post("/api/tables/{table_id}/fields", status_code=201)
def create_field(table_id: int, payload: FieldCreate):
    conn = get_db()
    _ensure_table_exists(conn, table_id)

    existing = conn.execute(
        "SELECT id FROM dynamic_fields WHERE table_id = ? AND field_name = ?",
        (table_id, payload.field_name),
    ).fetchone()
    if existing:
        conn.close()
        raise HTTPException(
            400, f"Field '{payload.field_name}' already exists in this table"
        )
    if payload.field_name in RESERVED_FIELD_NAMES:
        conn.close()
        raise HTTPException(400, f"Field name '{payload.field_name}' is reserved")

    max_order = conn.execute(
        "SELECT COALESCE(MAX(field_order), -1) FROM dynamic_fields WHERE table_id = ?",
        (table_id,),
    ).fetchone()[0]

    conn.execute(
        "INSERT INTO dynamic_fields (table_id, field_name, field_type, field_label, field_order) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            table_id,
            payload.field_name,
            payload.field_type,
            payload.field_label or payload.field_name,
            max_order + 1,
        ),
    )
    alter_table_for_new_field(conn, table_id, payload.field_name, payload.field_type)
    conn.commit()

    row = conn.execute(
        "SELECT * FROM dynamic_fields WHERE table_id = ? AND field_name = ?",
        (table_id, payload.field_name),
    ).fetchone()
    conn.close()
    return dict(row)


@app.put("/api/tables/{table_id}/fields/{field_id}")
def update_field(table_id: int, field_id: int, payload: FieldUpdate):
    conn = get_db()
    _ensure_table_exists(conn, table_id)

    row = conn.execute(
        "SELECT * FROM dynamic_fields WHERE id = ? AND table_id = ?",
        (field_id, table_id),
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Field not found")

    if payload.field_label is not None:
        conn.execute(
            "UPDATE dynamic_fields SET field_label = ? WHERE id = ?",
            (payload.field_label, field_id),
        )
    if payload.field_type is not None:
        conn.execute(
            "UPDATE dynamic_fields SET field_type = ? WHERE id = ?",
            (payload.field_type, field_id),
        )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM dynamic_fields WHERE id = ?", (field_id,)
    ).fetchone()
    conn.close()
    return dict(row)


@app.delete("/api/tables/{table_id}/fields/{field_id}")
def delete_field(table_id: int, field_id: int):
    conn = get_db()
    _ensure_table_exists(conn, table_id)

    row = conn.execute(
        "SELECT * FROM dynamic_fields WHERE id = ? AND table_id = ?",
        (field_id, table_id),
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Field not found")

    field_name = row["field_name"]
    conn.execute("DELETE FROM dynamic_fields WHERE id = ?", (field_id,))
    drop_column_from_table(conn, table_id, field_name)
    conn.commit()
    conn.close()
    return {"ok": True}


@app.post("/api/tables/{table_id}/fields/reorder")
def reorder_fields(table_id: int, order: list[int]):
    conn = get_db()
    _ensure_table_exists(conn, table_id)

    for idx, fid in enumerate(order):
        conn.execute(
            "UPDATE dynamic_fields SET field_order = ? WHERE id = ? AND table_id = ?",
            (idx, fid, table_id),
        )
    conn.commit()
    conn.close()
    return {"ok": True}


# ── Relationship management ───────────────────────────────────────────────────

SYSTEM_TABLES = {"users", "groups"}


class RelationshipCreate(BaseModel):
    to_table_id: int | None = None
    to_system_table: str | None = None
    rel_name: str
    rel_label: str = ""
    rel_type: str
    from_label: str = ""
    to_label: str = ""

    @model_validator(mode="after")
    def check_rel_type(self):
        if self.rel_type not in REL_TYPES:
            raise ValueError(f"rel_type must be one of {REL_TYPES}")
        if not self.to_table_id and not self.to_system_table:
            raise ValueError("Either to_table_id or to_system_table is required")
        if self.to_system_table and self.to_system_table not in SYSTEM_TABLES:
            raise ValueError(f"to_system_table must be one of {SYSTEM_TABLES}")
        return self


class RelationshipUpdate(BaseModel):
    rel_label: str | None = None
    from_label: str | None = None
    to_label: str | None = None


def _create_relationship_storage(conn: sqlite3.Connection, rel: dict):
    rel_id = rel["id"]
    rel_type = rel["rel_type"]
    from_table = get_items_table(rel["from_table_id"])
    to_system = rel.get("to_system_table")

    if to_system:
        to_table_ref = to_system
    else:
        to_table_ref = get_items_table(rel["to_table_id"])

    if rel_type in ("1-1", "1-n"):
        col = f"rel_{rel_id}"
        try:
            conn.execute(
                f"ALTER TABLE {from_table} ADD COLUMN {col} INTEGER REFERENCES {to_table_ref}(id)"
            )
        except sqlite3.OperationalError:
            pass
    elif rel_type == "n-n":
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS rel_{rel_id} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_item_id INTEGER NOT NULL REFERENCES {from_table}(id) ON DELETE CASCADE,
                to_item_id INTEGER NOT NULL REFERENCES {to_table_ref}(id) ON DELETE CASCADE,
                UNIQUE(from_item_id, to_item_id)
            )
        """)


def _drop_relationship_storage(conn: sqlite3.Connection, rel: dict):
    rel_id = rel["id"]
    rel_type = rel["rel_type"]

    if rel_type in ("1-1", "1-n"):
        col = f"rel_{rel_id}"
        drop_column_from_table(conn, rel["from_table_id"], col)
    elif rel_type == "n-n":
        conn.execute(f"DROP TABLE IF EXISTS rel_{rel_id}")


@app.get("/api/tables/{table_id}/relationships")
def list_relationships(table_id: int):
    conn = get_db()
    _ensure_table_exists(conn, table_id)
    rels = get_relationships(conn, table_id)
    conn.close()
    return rels


@app.post("/api/tables/{table_id}/relationships", status_code=201)
def create_relationship(table_id: int, payload: RelationshipCreate):
    conn = get_db()
    _ensure_table_exists(conn, table_id)
    if payload.to_table_id:
        _ensure_table_exists(conn, payload.to_table_id)

    if not payload.rel_name or not payload.rel_name.strip():
        conn.close()
        raise HTTPException(400, "Relationship name is required")

    existing = conn.execute(
        "SELECT id FROM dynamic_relationships WHERE from_table_id = ? AND rel_name = ?",
        (table_id, payload.rel_name),
    ).fetchone()
    if existing:
        conn.close()
        raise HTTPException(
            400, f"Relationship '{payload.rel_name}' already exists on this table"
        )

    conn.execute(
        "INSERT INTO dynamic_relationships "
        "(from_table_id, to_table_id, to_system_table, rel_name, rel_label, rel_type, from_label, to_label) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            table_id,
            payload.to_table_id,
            payload.to_system_table,
            payload.rel_name,
            payload.rel_label or payload.rel_name,
            payload.rel_type,
            payload.from_label,
            payload.to_label,
        ),
    )
    rel_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    row = conn.execute(
        "SELECT * FROM dynamic_relationships WHERE id = ?", (rel_id,)
    ).fetchone()
    rel = dict(row)
    _create_relationship_storage(conn, rel)
    conn.commit()
    conn.close()
    return rel


@app.put("/api/tables/{table_id}/relationships/{rel_id}")
def update_relationship(table_id: int, rel_id: int, payload: RelationshipUpdate):
    conn = get_db()
    _ensure_table_exists(conn, table_id)

    row = conn.execute(
        "SELECT * FROM dynamic_relationships WHERE id = ? AND (from_table_id = ? OR to_table_id = ?)",
        (rel_id, table_id, table_id),
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Relationship not found")

    if payload.rel_label is not None:
        conn.execute(
            "UPDATE dynamic_relationships SET rel_label = ? WHERE id = ?",
            (payload.rel_label, rel_id),
        )
    if payload.from_label is not None:
        conn.execute(
            "UPDATE dynamic_relationships SET from_label = ? WHERE id = ?",
            (payload.from_label, rel_id),
        )
    if payload.to_label is not None:
        conn.execute(
            "UPDATE dynamic_relationships SET to_label = ? WHERE id = ?",
            (payload.to_label, rel_id),
        )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM dynamic_relationships WHERE id = ?", (rel_id,)
    ).fetchone()
    conn.close()
    return dict(row)


@app.delete("/api/tables/{table_id}/relationships/{rel_id}")
def delete_relationship(table_id: int, rel_id: int):
    conn = get_db()
    _ensure_table_exists(conn, table_id)

    row = conn.execute(
        "SELECT * FROM dynamic_relationships WHERE id = ? AND (from_table_id = ? OR to_table_id = ?)",
        (rel_id, table_id, table_id),
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Relationship not found")

    _drop_relationship_storage(conn, dict(row))
    conn.execute("DELETE FROM dynamic_relationships WHERE id = ?", (rel_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


# ── Relationship link management ──────────────────────────────────────────────

class RelLinkSet(BaseModel):
    item_id: int
    target_ids: list[int]


@app.post("/api/tables/{table_id}/relationships/{rel_id}/link")
def set_relationship_links(table_id: int, rel_id: int, payload: RelLinkSet):
    conn = get_db()
    _ensure_table_exists(conn, table_id)

    row = conn.execute(
        "SELECT * FROM dynamic_relationships WHERE id = ? AND (from_table_id = ? OR to_table_id = ?)",
        (rel_id, table_id, table_id),
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Relationship not found")
    rel = dict(row)

    if rel["rel_type"] in ("1-1", "1-n"):
        if rel["from_table_id"] == table_id:
            items_table = get_items_table(table_id)
            col = f"rel_{rel_id}"
            val = payload.target_ids[0] if payload.target_ids else None
            conn.execute(
                f"UPDATE {items_table} SET {col} = ? WHERE id = ?",
                (val, payload.item_id),
            )
        else:
            other_table = get_items_table(rel["from_table_id"])
            col = f"rel_{rel_id}"
            conn.execute(
                f"UPDATE {other_table} SET {col} = NULL WHERE {col} = ?",
                (payload.item_id,),
            )
            for tid in payload.target_ids:
                conn.execute(
                    f"UPDATE {other_table} SET {col} = ? WHERE id = ?",
                    (payload.item_id, tid),
                )
    elif rel["rel_type"] == "n-n":
        junction = f"rel_{rel_id}"
        if rel["from_table_id"] == table_id:
            conn.execute(
                f"DELETE FROM {junction} WHERE from_item_id = ?",
                (payload.item_id,),
            )
            for tid in payload.target_ids:
                conn.execute(
                    f"INSERT OR IGNORE INTO {junction} (from_item_id, to_item_id) VALUES (?, ?)",
                    (payload.item_id, tid),
                )
        else:
            conn.execute(
                f"DELETE FROM {junction} WHERE to_item_id = ?",
                (payload.item_id,),
            )
            for tid in payload.target_ids:
                conn.execute(
                    f"INSERT OR IGNORE INTO {junction} (from_item_id, to_item_id) VALUES (?, ?)",
                    (tid, payload.item_id),
                )

    conn.commit()
    conn.close()
    return {"ok": True}


# ── CRUD items ────────────────────────────────────────────────────────────────

class ItemCreate(BaseModel):
    owner: str = "default"
    data: dict[str, Any] = {}


class ItemUpdate(BaseModel):
    owner: str | None = None
    data: dict[str, Any] | None = None


@app.get("/api/tables/{table_id}/items")
def list_items(
    table_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=1000),
    search: str | None = None,
    sort_by: str | None = None,
    sort_dir: str = "asc",
    user: dict | None = Depends(get_current_user_optional),
):
    conn = get_db()
    _ensure_table_exists(conn, table_id)
    if not check_table_permission(conn, table_id, "list", user):
        conn.close()
        raise HTTPException(403, "Not authorized to list items")
    fields = get_fields(conn, table_id)
    field_names = [f["field_name"] for f in fields]
    items_table = get_items_table(table_id)

    rels = get_relationships_from(conn, table_id)
    rel_cols = [f"rel_{r['id']}" for r in rels if r["rel_type"] in ("1-1", "1-n")]

    where_parts = []
    params: list = []

    row_filter = get_row_level_filter(conn, table_id, "list", user, params)
    if row_filter is not None:
        where_parts.append(row_filter)

    if search:
        search_cols = ["owner"] + field_names + rel_cols
        like_parts = " OR ".join(f"{c} LIKE ?" for c in search_cols)
        where_parts.append(f"({like_parts})")
        params.extend([f"%{search}%"] * len(search_cols))

    where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

    allowed_sort = ["id", "owner", "created_at", "updated_at"] + field_names + rel_cols
    if sort_by and sort_by in allowed_sort:
        direction = "DESC" if sort_dir.lower() == "desc" else "ASC"
        order_clause = f"ORDER BY {sort_by} {direction}"
    else:
        order_clause = "ORDER BY id DESC"

    count_sql = f"SELECT COUNT(*) FROM {items_table} {where_clause}"
    total = conn.execute(count_sql, params).fetchone()[0]

    offset = (page - 1) * page_size
    items_sql = (
        f"SELECT * FROM {items_table} {where_clause} {order_clause} LIMIT ? OFFSET ?"
    )
    rows = conn.execute(items_sql, params + [page_size, offset]).fetchall()

    items = [item_row_to_dict(r, fields) for r in rows]
    items = [enrich_item_with_relationships(conn, table_id, item) for item in items]
    conn.close()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }


@app.get("/api/tables/{table_id}/items/{item_id}")
def get_item(table_id: int, item_id: int, user: dict | None = Depends(get_current_user_optional)):
    conn = get_db()
    _ensure_table_exists(conn, table_id)
    if not check_table_permission(conn, table_id, "view", user):
        conn.close()
        raise HTTPException(403, "Not authorized to view items")
    fields = get_fields(conn, table_id)
    items_table = get_items_table(table_id)

    row = conn.execute(
        f"SELECT * FROM {items_table} WHERE id = ?", (item_id,)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Item not found")
    item = item_row_to_dict(row, fields)
    item = enrich_item_with_relationships(conn, table_id, item)
    conn.close()
    return item


@app.post("/api/tables/{table_id}/items", status_code=201)
def create_item(table_id: int, payload: ItemCreate, user: dict | None = Depends(get_current_user_optional)):
    conn = get_db()
    _ensure_table_exists(conn, table_id)
    if not check_table_permission(conn, table_id, "create", user):
        conn.close()
        raise HTTPException(403, "Not authorized to create items")
    fields = get_fields(conn, table_id)
    validated = validate_item_data(fields, payload.data)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    json_data = json.dumps(validated, ensure_ascii=False)
    items_table = get_items_table(table_id)

    conn.execute(
        f"INSERT INTO {items_table} (owner, data, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (payload.owner, json_data, now, now),
    )
    item_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    set_cols = ", ".join(f"{k} = ?" for k in validated if validated[k] is not None)
    set_vals = [v for v in validated.values() if v is not None]
    if set_cols:
        conn.execute(
            f"UPDATE {items_table} SET {set_cols} WHERE id = ?",
            set_vals + [item_id],
        )
    conn.commit()

    row = conn.execute(
        f"SELECT * FROM {items_table} WHERE id = ?", (item_id,)
    ).fetchone()
    item = item_row_to_dict(row, fields)
    item = enrich_item_with_relationships(conn, table_id, item)
    conn.close()
    return item


@app.put("/api/tables/{table_id}/items/{item_id}")
def update_item(table_id: int, item_id: int, payload: ItemUpdate, user: dict | None = Depends(get_current_user_optional)):
    conn = get_db()
    _ensure_table_exists(conn, table_id)
    if not check_table_permission(conn, table_id, "update", user):
        conn.close()
        raise HTTPException(403, "Not authorized to update items")
    fields = get_fields(conn, table_id)
    items_table = get_items_table(table_id)

    row = conn.execute(
        f"SELECT * FROM {items_table} WHERE id = ?", (item_id,)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Item not found")

    item = item_row_to_dict(row, fields)
    item = enrich_item_with_relationships(conn, table_id, item)
    if not check_table_permission(conn, table_id, "update", user, item):
        conn.close()
        raise HTTPException(403, "Not authorized to update this item")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    if payload.owner is not None:
        conn.execute(
            f"UPDATE {items_table} SET owner = ?, updated_at = ? WHERE id = ?",
            (payload.owner, now, item_id),
        )
    else:
        conn.execute(
            f"UPDATE {items_table} SET updated_at = ? WHERE id = ?",
            (now, item_id),
        )

    if payload.data is not None:
        validated = validate_item_data(fields, payload.data)
        json_data = json.dumps(validated, ensure_ascii=False)
        conn.execute(
            f"UPDATE {items_table} SET data = ? WHERE id = ?",
            (json_data, item_id),
        )
        set_cols = ", ".join(f"{k} = ?" for k in validated if validated[k] is not None)
        set_vals = [v for v in validated.values() if v is not None]
        if set_cols:
            conn.execute(
                f"UPDATE {items_table} SET {set_cols} WHERE id = ?",
                set_vals + [item_id],
            )

    conn.commit()
    row = conn.execute(
        f"SELECT * FROM {items_table} WHERE id = ?", (item_id,)
    ).fetchone()
    item = item_row_to_dict(row, fields)
    item = enrich_item_with_relationships(conn, table_id, item)
    conn.close()
    return item


@app.delete("/api/tables/{table_id}/items/{item_id}")
def delete_item(table_id: int, item_id: int, user: dict | None = Depends(get_current_user_optional)):
    conn = get_db()
    _ensure_table_exists(conn, table_id)
    if not check_table_permission(conn, table_id, "delete", user):
        conn.close()
        raise HTTPException(403, "Not authorized to delete items")
    fields = get_fields(conn, table_id)
    items_table = get_items_table(table_id)

    row = conn.execute(
        f"SELECT * FROM {items_table} WHERE id = ?", (item_id,)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Item not found")

    item = item_row_to_dict(row, fields)
    item = enrich_item_with_relationships(conn, table_id, item)
    if not check_table_permission(conn, table_id, "delete", user, item):
        conn.close()
        raise HTTPException(403, "Not authorized to delete this item")

    conn.execute(f"DELETE FROM {items_table} WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


# ── Serve frontend ────────────────────────────────────────────────────────────


# ── Auth & User management ────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str


class UserUpdate(BaseModel):
    name: str | None = None
    role: str | None = None

    @model_validator(mode="after")
    def check_role(self):
        if self.role is not None and self.role not in ("admin", "user"):
            raise ValueError("role must be 'admin' or 'user'")
        return self


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


@app.post("/api/auth/register", status_code=201)
def register(payload: RegisterRequest):
    conn = get_db()
    existing = get_user_by_email(conn, payload.email)
    if existing:
        conn.close()
        raise HTTPException(400, "Email already registered")

    user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    role = "admin" if user_count == 0 else "user"

    conn.execute(
        "INSERT INTO users (email, password_hash, name, role) VALUES (?, ?, ?, ?)",
        (payload.email, hash_password(payload.password), payload.name or payload.email.split("@")[0], role),
    )
    user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    user = get_user_by_id(conn, user_id)
    conn.close()

    token = create_access_token({"sub": str(user_id)})
    return {"access_token": token, "token_type": "bearer", "user": user}


@app.post("/api/auth/login")
def login(payload: LoginRequest):
    conn = get_db()
    user = get_user_by_email(conn, payload.email)
    if not user or not verify_password(payload.password, user["password_hash"]):
        conn.close()
        raise HTTPException(401, "Invalid email or password")
    conn.close()

    token = create_access_token({"sub": str(user["id"])})
    return {"access_token": token, "token_type": "bearer", "user": user}


@app.get("/api/auth/me")
def get_me(user: dict = Depends(get_current_user)):
    conn = get_db()
    groups = conn.execute(
        "SELECT g.* FROM groups g JOIN user_groups ug ON g.id = ug.group_id WHERE ug.user_id = ?",
        (user["id"],),
    ).fetchall()
    conn.close()
    user["groups"] = [dict(g) for g in groups]
    return user


@app.get("/api/users")
def list_users(admin: dict = Depends(require_admin)):
    conn = get_db()
    users = conn.execute("SELECT id, email, name, role, created_at FROM users ORDER BY id").fetchall()
    conn.close()
    return [dict(u) for u in users]


@app.put("/api/users/{user_id}")
def update_user(user_id: int, payload: UserUpdate, admin: dict = Depends(require_admin)):
    conn = get_db()
    user = get_user_by_id(conn, user_id)
    if not user:
        conn.close()
        raise HTTPException(404, "User not found")

    if payload.name is not None:
        conn.execute("UPDATE users SET name = ? WHERE id = ?", (payload.name, user_id))
    if payload.role is not None:
        conn.execute("UPDATE users SET role = ? WHERE id = ?", (payload.role, user_id))
    conn.commit()
    user = get_user_by_id(conn, user_id)
    conn.close()
    return user


@app.delete("/api/users/{user_id}")
def delete_user(user_id: int, admin: dict = Depends(require_admin)):
    conn = get_db()
    user = get_user_by_id(conn, user_id)
    if not user:
        conn.close()
        raise HTTPException(404, "User not found")
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


@app.post("/api/users/{user_id}/make-admin")
def make_admin(user_id: int, admin: dict = Depends(require_admin)):
    conn = get_db()
    user = get_user_by_id(conn, user_id)
    if not user:
        conn.close()
        raise HTTPException(404, "User not found")
    conn.execute("UPDATE users SET role = 'admin' WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


@app.post("/api/users/{user_id}/remove-admin")
def remove_admin(user_id: int, admin: dict = Depends(require_admin)):
    conn = get_db()
    user = get_user_by_id(conn, user_id)
    if not user:
        conn.close()
        raise HTTPException(404, "User not found")
    if user["role"] == "admin":
        admin_count = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()[0]
        if admin_count <= 1:
            conn.close()
            raise HTTPException(400, "Cannot remove the last admin")
    conn.execute("UPDATE users SET role = 'user' WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


# ── Group management ──────────────────────────────────────────────────────────

class GroupCreate(BaseModel):
    name: str
    description: str = ""


class GroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class GroupMemberAction(BaseModel):
    user_id: int


@app.get("/api/groups")
def list_groups(admin: dict = Depends(require_admin)):
    conn = get_db()
    groups = conn.execute("SELECT * FROM groups ORDER BY id").fetchall()
    conn.close()
    return [dict(g) for g in groups]


@app.post("/api/groups", status_code=201)
def create_group(payload: GroupCreate, admin: dict = Depends(require_admin)):
    conn = get_db()
    existing = conn.execute("SELECT id FROM groups WHERE name = ?", (payload.name,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(400, f"Group '{payload.name}' already exists")
    conn.execute(
        "INSERT INTO groups (name, description) VALUES (?, ?)",
        (payload.name, payload.description),
    )
    group_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    group = dict(conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone())
    conn.close()
    return group


@app.put("/api/groups/{group_id}")
def update_group(group_id: int, payload: GroupUpdate, admin: dict = Depends(require_admin)):
    conn = get_db()
    group = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
    if not group:
        conn.close()
        raise HTTPException(404, "Group not found")
    if payload.name is not None:
        conn.execute("UPDATE groups SET name = ? WHERE id = ?", (payload.name, group_id))
    if payload.description is not None:
        conn.execute("UPDATE groups SET description = ? WHERE id = ?", (payload.description, group_id))
    conn.commit()
    group = dict(conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone())
    conn.close()
    return group


@app.delete("/api/groups/{group_id}")
def delete_group(group_id: int, admin: dict = Depends(require_admin)):
    conn = get_db()
    group = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
    if not group:
        conn.close()
        raise HTTPException(404, "Group not found")
    conn.execute("DELETE FROM groups WHERE id = ?", (group_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


@app.get("/api/groups/{group_id}/members")
def list_group_members(group_id: int, admin: dict = Depends(require_admin)):
    conn = get_db()
    members = conn.execute(
        "SELECT u.id, u.email, u.name, u.role FROM users u "
        "JOIN user_groups ug ON u.id = ug.user_id WHERE ug.group_id = ?",
        (group_id,),
    ).fetchall()
    conn.close()
    return [dict(m) for m in members]


@app.post("/api/groups/{group_id}/members", status_code=201)
def add_group_member(group_id: int, payload: GroupMemberAction, admin: dict = Depends(require_admin)):
    conn = get_db()
    group = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
    if not group:
        conn.close()
        raise HTTPException(404, "Group not found")
    user = get_user_by_id(conn, payload.user_id)
    if not user:
        conn.close()
        raise HTTPException(404, "User not found")
    try:
        conn.execute("INSERT INTO user_groups (user_id, group_id) VALUES (?, ?)", (payload.user_id, group_id))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()
    return {"ok": True}


@app.delete("/api/groups/{group_id}/members/{user_id}")
def remove_group_member(group_id: int, user_id: int, admin: dict = Depends(require_admin)):
    conn = get_db()
    conn.execute("DELETE FROM user_groups WHERE user_id = ? AND group_id = ?", (user_id, group_id))
    conn.commit()
    conn.close()
    return {"ok": True}


# ── System table items (for relationship dropdowns) ───────────────────────────

@app.get("/api/system/users")
def list_system_users(user: dict = Depends(get_current_user)):
    conn = get_db()
    rows = conn.execute("SELECT id, name, email FROM users ORDER BY id").fetchall()
    conn.close()
    return [{"id": r["id"], "label": r["name"] or r["email"]} for r in rows]


@app.get("/api/system/groups")
def list_system_groups(user: dict = Depends(get_current_user)):
    conn = get_db()
    rows = conn.execute("SELECT id, name FROM groups ORDER BY id").fetchall()
    conn.close()
    return [{"id": r["id"], "label": r["name"]} for r in rows]


# ── Permission management ─────────────────────────────────────────────────────

class PermissionCreate(BaseModel):
    target_type: str
    target_id: int | None = None
    target_role: str | None = None
    list_rule: str | None = None
    view_rule: str | None = None
    create_rule: str | None = None
    update_rule: str | None = None
    delete_rule: str | None = None

    @model_validator(mode="after")
    def check_target(self):
        if self.target_type not in ("user", "group", "role"):
            raise ValueError("target_type must be 'user', 'group', or 'role'")
        return self


class PermissionUpdate(BaseModel):
    list_rule: str | None = None
    view_rule: str | None = None
    create_rule: str | None = None
    update_rule: str | None = None
    delete_rule: str | None = None


@app.get("/api/tables/{table_id}/permissions")
def list_permissions(table_id: int, admin: dict = Depends(require_admin)):
    conn = get_db()
    _ensure_table_exists(conn, table_id)
    perms = conn.execute(
        "SELECT * FROM permissions WHERE table_id = ?", (table_id,)
    ).fetchall()
    conn.close()
    return [dict(p) for p in perms]


@app.post("/api/tables/{table_id}/permissions", status_code=201)
def create_permission(table_id: int, payload: PermissionCreate, admin: dict = Depends(require_admin)):
    conn = get_db()
    _ensure_table_exists(conn, table_id)

    conn.execute(
        "INSERT INTO permissions (table_id, target_type, target_id, target_role, "
        "list_rule, view_rule, create_rule, update_rule, delete_rule) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (table_id, payload.target_type, payload.target_id, payload.target_role,
         payload.list_rule, payload.view_rule, payload.create_rule,
         payload.update_rule, payload.delete_rule),
    )
    perm_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    perm = dict(conn.execute("SELECT * FROM permissions WHERE id = ?", (perm_id,)).fetchone())
    conn.close()
    return perm


@app.put("/api/tables/{table_id}/permissions/{perm_id}")
def update_permission(table_id: int, perm_id: int, payload: PermissionUpdate, admin: dict = Depends(require_admin)):
    conn = get_db()
    _ensure_table_exists(conn, table_id)
    perm = conn.execute(
        "SELECT * FROM permissions WHERE id = ? AND table_id = ?", (perm_id, table_id)
    ).fetchone()
    if not perm:
        conn.close()
        raise HTTPException(404, "Permission not found")

    for field in ("list_rule", "view_rule", "create_rule", "update_rule", "delete_rule"):
        val = getattr(payload, field)
        if val is not None:
            conn.execute(f"UPDATE permissions SET {field} = ? WHERE id = ?", (val, perm_id))
    conn.commit()
    perm = dict(conn.execute("SELECT * FROM permissions WHERE id = ?", (perm_id,)).fetchone())
    conn.close()
    return perm


@app.delete("/api/tables/{table_id}/permissions/{perm_id}")
def delete_permission(table_id: int, perm_id: int, admin: dict = Depends(require_admin)):
    conn = get_db()
    _ensure_table_exists(conn, table_id)
    perm = conn.execute(
        "SELECT * FROM permissions WHERE id = ? AND table_id = ?", (perm_id, table_id)
    ).fetchone()
    if not perm:
        conn.close()
        raise HTTPException(404, "Permission not found")
    conn.execute("DELETE FROM permissions WHERE id = ?", (perm_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


@app.get("/api/tables/{table_id}/my-permissions")
def get_my_permissions(table_id: int, user: dict = Depends(get_current_user)):
    conn = get_db()
    _ensure_table_exists(conn, table_id)
    perms = get_user_permissions(conn, table_id, user)
    conn.close()
    return perms


# ── File management ───────────────────────────────────────────────────────────

@app.post("/api/tables/{table_id}/items/{item_id}/files", status_code=201)
def upload_file(
    table_id: int,
    item_id: int,
    file: UploadFile = FastAPIFile(...),
    field_name: str = Form(""),
    user: dict = Depends(get_current_user),
):
    conn = get_db()
    _ensure_table_exists(conn, table_id)
    items_table = get_items_table(table_id)
    row = conn.execute(f"SELECT * FROM {items_table} WHERE id = ?", (item_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Item not found")

    check_table_permission(conn, table_id, "update", user, dict(row))

    data = file.file.read()
    conn.execute(
        "INSERT INTO files (table_id, item_id, field_name, filename, mime_type, size, data, uploader_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (table_id, item_id, field_name, file.filename, file.content_type or "application/octet-stream",
         len(data), data, user["id"]),
    )
    file_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    f = dict(conn.execute(
        "SELECT id, table_id, item_id, field_name, filename, mime_type, size, uploader_id, created_at FROM files WHERE id = ?",
        (file_id,),
    ).fetchone())
    conn.close()
    return f


@app.get("/api/tables/{table_id}/items/{item_id}/files")
def list_files(table_id: int, item_id: int, user: dict = Depends(get_current_user)):
    conn = get_db()
    _ensure_table_exists(conn, table_id)
    check_table_permission(conn, table_id, "view", user)
    files = conn.execute(
        "SELECT id, table_id, item_id, field_name, filename, mime_type, size, uploader_id, created_at "
        "FROM files WHERE table_id = ? AND item_id = ?",
        (table_id, item_id),
    ).fetchall()
    conn.close()
    return [dict(f) for f in files]


@app.get("/api/files/{file_id}")
def download_file(file_id: int, user: dict = Depends(get_current_user)):
    conn = get_db()
    f = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
    if not f:
        conn.close()
        raise HTTPException(404, "File not found")
    check_table_permission(conn, f["table_id"], "view", user)
    conn.close()
    return Response(
        content=f["data"],
        media_type=f["mime_type"],
        headers={"Content-Disposition": f'attachment; filename="{f["filename"]}"'},
    )


@app.delete("/api/files/{file_id}")
def delete_file(file_id: int, user: dict = Depends(get_current_user)):
    conn = get_db()
    f = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
    if not f:
        conn.close()
        raise HTTPException(404, "File not found")
    check_table_permission(conn, f["table_id"], "update", user)
    conn.execute("DELETE FROM files WHERE id = ?", (file_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


# ── Comments ──────────────────────────────────────────────────────────────────

class CommentCreate(BaseModel):
    content: str


class CommentUpdate(BaseModel):
    content: str


@app.get("/api/tables/{table_id}/items/{item_id}/comments")
def list_comments(table_id: int, item_id: int, user: dict = Depends(get_current_user)):
    conn = get_db()
    _ensure_table_exists(conn, table_id)
    check_table_permission(conn, table_id, "view", user)
    comments = conn.execute(
        "SELECT c.*, u.name as user_name, u.email as user_email FROM comments c "
        "JOIN users u ON c.user_id = u.id "
        "WHERE c.table_id = ? AND c.item_id = ? ORDER BY c.created_at",
        (table_id, item_id),
    ).fetchall()
    conn.close()
    return [dict(c) for c in comments]


@app.post("/api/tables/{table_id}/items/{item_id}/comments", status_code=201)
def create_comment(
    table_id: int, item_id: int, payload: CommentCreate, user: dict = Depends(get_current_user)
):
    conn = get_db()
    _ensure_table_exists(conn, table_id)
    items_table = get_items_table(table_id)
    row = conn.execute(f"SELECT * FROM {items_table} WHERE id = ?", (item_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Item not found")

    if not check_table_permission(conn, table_id, "update", user, dict(row)):
        conn.close()
        raise HTTPException(403, "Not authorized to comment on this item")

    conn.execute(
        "INSERT INTO comments (table_id, item_id, user_id, content) VALUES (?, ?, ?, ?)",
        (table_id, item_id, user["id"], payload.content),
    )
    comment_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    comment = dict(conn.execute(
        "SELECT c.*, u.name as user_name, u.email as user_email FROM comments c "
        "JOIN users u ON c.user_id = u.id WHERE c.id = ?", (comment_id,)
    ).fetchone())
    conn.close()
    return comment


@app.put("/api/comments/{comment_id}")
def update_comment(comment_id: int, payload: CommentUpdate, user: dict = Depends(get_current_user)):
    conn = get_db()
    comment = conn.execute("SELECT * FROM comments WHERE id = ?", (comment_id,)).fetchone()
    if not comment:
        conn.close()
        raise HTTPException(404, "Comment not found")
    if comment["user_id"] != user["id"] and user["role"] != "admin":
        conn.close()
        raise HTTPException(403, "Can only edit your own comments")
    conn.execute(
        "UPDATE comments SET content = ?, updated_at = datetime('now') WHERE id = ?",
        (payload.content, comment_id),
    )
    conn.commit()
    comment = dict(conn.execute(
        "SELECT c.*, u.name as user_name, u.email as user_email FROM comments c "
        "JOIN users u ON c.user_id = u.id WHERE c.id = ?", (comment_id,)
    ).fetchone())
    conn.close()
    return comment


@app.delete("/api/comments/{comment_id}")
def delete_comment(comment_id: int, user: dict = Depends(get_current_user)):
    conn = get_db()
    comment = conn.execute("SELECT * FROM comments WHERE id = ?", (comment_id,)).fetchone()
    if not comment:
        conn.close()
        raise HTTPException(404, "Comment not found")
    if comment["user_id"] != user["id"] and user["role"] != "admin":
        conn.close()
        raise HTTPException(403, "Can only delete your own comments")
    conn.execute("DELETE FROM comments WHERE id = ?", (comment_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


# ── Serve frontend ────────────────────────────────────────────────────────────
STATIC_DIR.mkdir(exist_ok=True)
assets_dir = STATIC_DIR / "assets"
if assets_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="static_assets")


@app.get("/{path:path}")
async def serve_frontend(path: str):
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    raise HTTPException(404, "Not found")
