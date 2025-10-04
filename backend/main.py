from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import date, datetime
from typing import List, Optional
from PIL import Image
import io

from backend.database import Base, engine, SessionLocal
from backend import models
from backend import schemas
from backend.auth import get_db, get_password_hash, verify_password, create_access_token, get_current_user, require_role
from backend.currency import get_company_currency_for_country, convert
from backend.workflow import evaluate_rules, advance_sequence_if_needed
from backend.ocr import ocr_text, detect_currency_and_amount

app = FastAPI(title="Expense Approvals API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

# ---- Auth & Bootstrap ----

@app.post("/auth/signup", response_model=schemas.TokenResponse)
def signup(payload: schemas.SignupRequest, db: Session = Depends(get_db)):
    # Create Company
    currency = get_company_currency_for_country(payload.country_code)
    if not currency:
        raise HTTPException(status_code=400, detail="Could not determine currency for country")
    company = models.Company(name=payload.company_name, country_code=payload.country_code.upper(), currency_code=currency)
    db.add(company)
    db.flush()

    # Create Admin
    if db.query(models.User).filter(models.User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    admin = models.User(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=get_password_hash(payload.password),
        role=models.Role.admin,
        company_id=company.id,
        is_manager_approver=True,
    )
    db.add(admin)
    db.commit()
    token = create_access_token({"sub": str(admin.id)})
    return schemas.TokenResponse(access_token=token)

@app.post("/auth/login", response_model=schemas.TokenResponse)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": str(user.id)})
    return schemas.TokenResponse(access_token=token)

@app.get("/auth/me", response_model=schemas.UserOut)
def me(user: models.User = Depends(get_current_user)):
    return user

# ---- Admin: Users & Rules ----

@app.post("/admin/users", response_model=schemas.UserOut)
def create_user(payload: schemas.CreateUserRequest, admin: models.User = Depends(require_role(models.Role.admin)), db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already exists")
    user = models.User(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=get_password_hash(payload.password),
        role=payload.role,
        company_id=admin.company_id,
        manager_id=payload.manager_id,
        is_manager_approver=payload.is_manager_approver
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@app.get("/admin/users", response_model=List[schemas.UserOut])
def list_users(admin: models.User = Depends(require_role(models.Role.admin)), db: Session = Depends(get_db)):
    return db.query(models.User).filter(models.User.company_id == admin.company_id).all()

@app.post("/admin/rules", response_model=schemas.ApprovalRuleOut)
def create_rule(payload: schemas.ApprovalRuleCreate, admin: models.User = Depends(require_role(models.Role.admin)), db: Session = Depends(get_db)):
    rule = models.ApprovalRule(
        company_id=admin.company_id,
        type=models.RuleType(payload.type.value),
        threshold_percent=payload.threshold_percent,
        specific_user_id=payload.specific_user_id
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule

@app.get("/admin/rules", response_model=List[schemas.ApprovalRuleOut])
def list_rules(admin: models.User = Depends(require_role(models.Role.admin)), db: Session = Depends(get_db)):
    return db.query(models.ApprovalRule).filter(models.ApprovalRule.company_id == admin.company_id).all()

# ---- Employee: Submit & View ----

def build_sequence_for_expense(db: Session, employee: models.User) -> list[models.ExpenseApprovalStep]:
    steps: list[models.ExpenseApprovalStep] = []
    seq = 1
    # Step 1: manager if IS MANAGER APPROVER
    if employee.manager_id:
        mgr = db.get(models.User, employee.manager_id)
        if mgr and mgr.is_manager_approver:
            steps.append(models.ExpenseApprovalStep(approver_user_id=mgr.id, sequence=seq)); seq += 1
    # Admin may define arbitrary others; for demo we auto-add any managers (excluding employee/manager) in same company, sorted by id, up to 2 roles:
    managers = db.query(models.User).filter(models.User.company_id==employee.company_id, models.User.role==models.Role.manager).order_by(models.User.id).all()
    for m in managers:
        if m.id in [employee.id, employee.manager_id]:
            continue
        steps.append(models.ExpenseApprovalStep(approver_user_id=m.id, sequence=seq))
        seq += 1
        if seq>5: break
    return steps

@app.post("/expenses", response_model=schemas.ExpenseOut)
def submit_expense(payload: schemas.ExpenseCreate, user: models.User = Depends(require_role(models.Role.employee, models.Role.manager, models.Role.admin)), db: Session = Depends(get_db)):
    company = db.get(models.Company, user.company_id)
    normalized = convert(payload.amount, payload.currency_code, company.currency_code)
    exp = models.Expense(
        employee_id=user.id,
        amount=payload.amount,
        currency_code=payload.currency_code.upper(),
        normalized_amount=normalized,
        category=payload.category,
        description=payload.description,
        date=payload.date,
        status=models.ExpenseStatus.pending,
    )
    db.add(exp)
    db.flush()
    # Build steps
    steps = build_sequence_for_expense(db, user)
    for s in steps:
        s.expense_id = exp.id
        db.add(s)
    db.commit()
    db.refresh(exp)
    advance_sequence_if_needed(exp)
    db.commit()
    return exp

@app.get("/expenses/my", response_model=List[schemas.ExpenseOut])
def my_expenses(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(models.Expense).filter(models.Expense.employee_id == user.id).order_by(models.Expense.created_at.desc()).all()

# ---- Approvals ----

@app.get("/approvals/pending", response_model=List[schemas.ExpenseOut])
def pending_for_me(user: models.User = Depends(require_role(models.Role.manager, models.Role.admin)), db: Session = Depends(get_db)):
    step_q = db.query(models.ExpenseApprovalStep).filter(
        models.ExpenseApprovalStep.approver_user_id == user.id,
        models.ExpenseApprovalStep.status == models.StepDecision.pending
    )
    expense_ids = [s.expense_id for s in step_q]
    if not expense_ids:
        return []
    exps = db.query(models.Expense).filter(models.Expense.id.in_(expense_ids)).all()
    return exps

@app.post("/approvals/{expense_id}/act", response_model=schemas.ExpenseOut)
def act_on_expense(expense_id: int, payload: schemas.StepAction, user: models.User = Depends(require_role(models.Role.manager, models.Role.admin)), db: Session = Depends(get_db)):
    exp = db.get(models.Expense, expense_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Expense not found")

    # Find my pending step
    step = db.query(models.ExpenseApprovalStep).filter(
        models.ExpenseApprovalStep.expense_id == expense_id,
        models.ExpenseApprovalStep.approver_user_id == user.id,
        models.ExpenseApprovalStep.status == models.StepDecision.pending
    ).order_by(models.ExpenseApprovalStep.sequence).first()

    if not step:
        raise HTTPException(status_code=400, detail="No pending step for this user")

    step.status = models.StepDecision.approved if payload.approve else models.StepDecision.rejected
    step.comment = payload.comment
    step.decided_at = datetime.utcnow()
    db.commit()

    # Evaluate rules & advance
    evaluate_rules(db, exp)
    advance_sequence_if_needed(exp)
    db.commit()
    db.refresh(exp)
    return exp

@app.get("/expenses/{expense_id}/steps", response_model=List[schemas.StepOut])
def list_steps(expense_id: int, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    exp = db.get(models.Expense, expense_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Expense not found")
    # Visibility: employee or any approver/admin in same company
    if user.company_id != exp.employee.company_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    steps = db.query(models.ExpenseApprovalStep).filter(models.ExpenseApprovalStep.expense_id == expense_id).order_by(models.ExpenseApprovalStep.sequence).all()
    return steps

# ---- OCR ----

@app.post("/ocr/parse", response_model=schemas.OCRResult)
def parse_receipt(file: UploadFile = File(...)):
    content = file.file.read()
    img = Image.open(io.BytesIO(content)).convert("RGB")
    text = ocr_text(img)
    currency, amount = detect_currency_and_amount(text)
    return schemas.OCRResult(amount=amount, currency_code=currency, raw_text=text)
