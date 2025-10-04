from sqlalchemy.orm import Session
from backend import models
from datetime import datetime

def evaluate_rules(db: Session, expense: models.Expense):
    """Re-evaluate conditional rules after each step decision."""
    company_id = expense.employee.company_id
    rules = db.query(models.ApprovalRule).filter(models.ApprovalRule.company_id == company_id).all()

    # Gather step stats
    steps = sorted(expense.steps, key=lambda s: s.sequence)
    total = len(steps)
    approved = sum(1 for s in steps if s.status == models.StepDecision.approved)
    rejected = any(s.status == models.StepDecision.rejected for s in steps)

    if rejected:
        expense.status = models.ExpenseStatus.rejected
        return

    for r in rules:
        if r.type == models.RuleType.percentage and r.threshold_percent:
            if total > 0 and (approved / total) * 100.0 >= r.threshold_percent:
                expense.status = models.ExpenseStatus.approved
                return
        elif r.type == models.RuleType.specific and r.specific_user_id:
            # If specific approver has approved, auto-approve
            if any(s.approver_user_id == r.specific_user_id and s.status == models.StepDecision.approved for s in steps):
                expense.status = models.ExpenseStatus.approved
                return
        elif r.type == models.RuleType.hybrid:
            pct_ok = total > 0 and r.threshold_percent and (approved / total) * 100.0 >= r.threshold_percent
            spec_ok = r.specific_user_id and any(s.approver_user_id == r.specific_user_id and s.status == models.StepDecision.approved for s in steps)
            if pct_ok or spec_ok:
                expense.status = models.ExpenseStatus.approved
                return

    # If no rule finalized the decision, fall back to sequence flow:
    # Approve only when all steps approved
    if all(s.status == models.StepDecision.approved for s in steps if steps):
        expense.status = models.ExpenseStatus.approved

def advance_sequence_if_needed(expense: models.Expense):
    """Move pointer to next pending step, if current is done."""
    ordered = sorted(expense.steps, key=lambda s: s.sequence)
    for idx, step in enumerate(ordered):
        if step.status == models.StepDecision.pending:
            expense.current_step_index = idx
            return
    # No pending steps remain
    expense.current_step_index = len(ordered)
