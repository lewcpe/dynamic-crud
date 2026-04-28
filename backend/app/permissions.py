import re
from .database import get_db, get_relationships_from


def check_table_permission(conn, table_id: int, action: str, user: dict | None, item: dict | None = None) -> bool:
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


def evaluate_rule(rule: str, user: dict | None, item: dict | None, conn, table_id: int = 0) -> bool:
    if not rule or not rule.strip():
        return True

    rule = rule.strip()

    if rule == '@request.auth.id != ""':
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


def get_row_level_filter(conn, table_id: int, action: str, user: dict | None, params: list) -> str | None:
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


def get_user_permissions(conn, table_id: int, user: dict | None) -> dict:
    actions = ["list", "view", "create", "update", "delete"]
    result = {}
    for action in actions:
        result[action] = check_table_permission(conn, table_id, action, user)
    return result


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

    def __init__(self, rule: str, user: dict | None, table_id: int, conn):
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
            return self._relationship_to_sql(node[1], node[2], params)
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
