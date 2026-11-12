from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SplitEqual(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["equal"]
    members: list[str] = Field(..., min_length=1)


class SplitExact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["exact"]
    shares: dict[str, str] = Field(...)


class CreateExpenseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str
    paid_by: str
    amount: str
    split: SplitEqual | SplitExact


class ExpenseShareResponse(BaseModel):
    username: str
    amount: str


class ExpenseResponse(BaseModel):
    id: int
    group_id: int
    description: str
    paid_by: str
    amount: str
    created_at: str
    deleted_at: str | None = None
    shares: list[ExpenseShareResponse]


class GroupResponse(BaseModel):
    id: int
    name: str
    members: list[str]


class BalanceItem(BaseModel):
    username: str
    balance: str


class GroupBalancesResponse(BaseModel):
    group_id: int
    balances: list[BalanceItem]
