from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import date, datetime
from enum import Enum

class Role(str, Enum):
    admin = "admin"
    manager = "manager"
    employee = "employee"

class SignupRequest(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    company_name: str
    country_code: str  # e.g., 'US', 'IN'

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    role: Role
    manager_id: Optional[int] = None
    is_manager_approver: bool

    class Config:
        from_attributes = True

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class CreateUserRequest(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    role: Role
    manager_id: Optional[int] = None
    is_manager_approver: bool = False

class ExpenseCreate(BaseModel):
    amount: float
    currency_code: str
    category: str
    description: Optional[str] = None
    date: date

class ExpenseOut(BaseModel):
    id: int
    employee_id: int
    amount: float
    currency_code: str
    normalized_amount: float
    category: str
    description: Optional[str]
    date: date
    status: str
    current_step_index: int

    class Config:
        from_attributes = True

class StepAction(BaseModel):
    approve: bool
    comment: Optional[str] = None

class StepOut(BaseModel):
    id: int
    approver_user_id: int
    sequence: int
    status: str
    comment: Optional[str]
    decided_at: Optional[datetime]

    class Config:
        from_attributes = True

class RuleType(str, Enum):
    percentage = "percentage"
    specific = "specific"
    hybrid = "hybrid"

class ApprovalRuleCreate(BaseModel):
    type: RuleType
    threshold_percent: Optional[int] = Field(None, ge=1, le=100)
    specific_user_id: Optional[int] = None

class ApprovalRuleOut(BaseModel):
    id: int
    type: RuleType
    threshold_percent: Optional[int]
    specific_user_id: Optional[int]

    class Config:
        from_attributes = True

class OCRResult(BaseModel):
    amount: Optional[float]
    currency_code: Optional[str]
    raw_text: str
