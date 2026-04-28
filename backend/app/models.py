from typing import Any
from pydantic import BaseModel, model_validator
from .database import FIELD_TYPES, REL_TYPES, SYSTEM_TABLES


class TableCreate(BaseModel):
    name: str
    label: str = ""
    represent: str = ""


class TableUpdate(BaseModel):
    name: str | None = None
    label: str | None = None
    represent: str | None = None


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


class RelLinkSet(BaseModel):
    item_id: int
    target_ids: list[int]


class ItemCreate(BaseModel):
    owner: str = "default"
    data: dict[str, Any] = {}


class ItemUpdate(BaseModel):
    owner: str | None = None
    data: dict[str, Any] | None = None


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


class GroupCreate(BaseModel):
    name: str
    description: str = ""


class GroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class GroupMemberAction(BaseModel):
    user_id: int


class SetManager(BaseModel):
    manager_id: int | None = None


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


class CommentCreate(BaseModel):
    content: str


class CommentUpdate(BaseModel):
    content: str
