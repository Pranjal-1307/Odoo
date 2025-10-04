from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, Float, Date, DateTime, Text, Enum
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime
from backend.database import Base
import enum

class Role(str, enum.Enum):
    admin = "admin"
    manager = "manager"
    employee = "employee"

class Company(Base):
    __tablename__ = "companies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    country_code: Mapped[str] = mapped_column(String, nullable=False)
    currency_code: Mapped[str] = mapped_column(String, nullable=False)

    users = relationship("User", back_populates="company")
    approval_rules = relationship("ApprovalRule", back_populates="company")

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[Role] = mapped_column(Enum(Role), nullable=False, default=Role.employee)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    manager_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    is_manager_approver: Mapped[bool] = mapped_column(Boolean, default=False)

    company = relationship("Company", back_populates="users")
    manager = relationship("User", remote_side=[id])

class ExpenseStatus(str, enum.Enum):
    draft = "draft"
    pending = "pending"
    approved = "approved"
    rejected = "rejected"

class Expense(Base):
    __tablename__ = "expenses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency_code: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    date: Mapped[Date] = mapped_column(Date, nullable=False)
    normalized_amount: Mapped[float] = mapped_column(Float, default=0.0)  # in company currency
    status: Mapped[ExpenseStatus] = mapped_column(Enum(ExpenseStatus), default=ExpenseStatus.pending)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    current_step_index: Mapped[int] = mapped_column(Integer, default=0)

    employee = relationship("User")
    steps = relationship("ExpenseApprovalStep", back_populates="expense", cascade="all, delete-orphan")

class StepDecision(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"

class ExpenseApprovalStep(Base):
    __tablename__ = "expense_approval_steps"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    expense_id: Mapped[int] = mapped_column(Integer, ForeignKey("expenses.id"))
    approver_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[StepDecision] = mapped_column(Enum(StepDecision), default=StepDecision.pending)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    expense = relationship("Expense", back_populates="steps")
    approver = relationship("User")

class RuleType(str, enum.Enum):
    percentage = "percentage"
    specific = "specific"
    hybrid = "hybrid"

class ApprovalRule(Base):
    __tablename__ = "approval_rules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"))
    type: Mapped[RuleType] = mapped_column(Enum(RuleType), nullable=False)
    threshold_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)  # e.g., 60
    specific_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)

    company = relationship("Company", back_populates="approval_rules")
    specific_user = relationship("User")
