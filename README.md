# Expense Reimbursements with Multi-Approver & Conditional Rules + OCR

A minimal-but-complete FastAPI project demonstrating:

- Company bootstrap on signup (company currency auto-set based on selected country).
- Roles: Admin, Manager, Employee with JWT auth and RBAC.
- Expense submission in any currency; normalization to company currency using live FX.
- Multi-step approval (sequence: Manager → Finance → Director, etc.).
- Conditional approvals:
  - Percentage rule (e.g., 60% approvers approve → expense approved).
  - Specific approver auto-approve (e.g., CFO approves → auto-approved).
  - Hybrid (percentage OR specific approver).
- OCR for receipts (amount + currency detection) with pytesseract + OpenCV.
- Simple demo frontend (static HTML/JS).

## Quickstart

```bash
# 1) Create & activate a venv (recommended)
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2) Install deps
pip install -r requirements.txt

# 3) Start API
uvicorn backend.main:app --reload

# 4) Open demo UI
# Serve the 'frontend' folder (e.g., with Python http.server)
python -m http.server --directory frontend 8080
# Visit http://localhost:8080
```

## Notes

- OCR requires Tesseract binary to be installed on your system.
  - macOS: `brew install tesseract`
  - Ubuntu/Debian: `sudo apt-get install tesseract-ocr`
  - Windows: Install from https://github.com/UB-Mannheim/tesseract/wiki
- The API endpoints are documented via Swagger at `http://127.0.0.1:8000/docs`.
- Currency APIs used:
  - Countries & currencies: `https://restcountries.com/v3.1/all?fields=name,currencies`
  - Rates: `https://api.exchangerate-api.com/v4/latest/{BASE_CURRENCY}`

## Example Users & Flow

1. Sign up as Admin → automatically creates a Company (choose country) and Admin user.
2. Admin creates Employees & Managers; defines manager relationships.
3. Employee submits an expense (in any currency).
4. System normalizes to company currency and kicks off approval sequence.
5. Approvers act in order; conditional rules are applied after each decision.
6. Expense is Approved or Rejected; history is visible to the employee.

## Testing

```bash
pytest -q
```
