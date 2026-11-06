Digital Wallet & Payments System

A backend digital wallet and payment management system developed using FastAPI, Python, SQLAlchemy, and MySQL.

The project demonstrates secure wallet transactions, role-based authentication, double-entry accounting, merchant payments, cashback, refunds, bank withdrawals, fraud detection, and transaction statements.

Tech Stack

- Backend: Python, FastAPI, Pydantic
- Database: MySQL, SQLAlchemy
- Database Migrations: Alembic
- Authentication: JWT, password hashing
- Security: Transaction PIN, OTP verification
- Payment Accounting: Double-entry ledger using Decimal
- PDF Statements: ReportLab
- CSV Statements: Python CSV module
- QR Codes: qrcode
- Scheduled Jobs: APScheduler
- Email: SMTP
- API Testing: Swagger UI
- Server: Uvicorn

Implemented Features

Authentication and Wallet Management

- User registration and login
- JWT authentication and role-based access
- Wallet creation and balance management
- Transaction PIN creation, verification, and modification
- OTP verification
- Wallet freezing and KYC management

Wallet Transactions

- Add money
- Peer-to-peer transfers
- Merchant payments
- Merchant refunds
- Cashback processing
- Bank withdrawals and withdrawal reversals
- Transaction history

Double-Entry Ledger

Each money movement is recorded through debit and credit ledger entries.

The system maintains separate accounts for user wallets, merchant wallets, bank settlement, cashback, platform fees, withdrawal clearing, and held funds.

Example: Adding ₹100 to a user wallet

Account| Entry| Amount
Bank Settlement| Debit| ₹100
User Wallet| Credit| ₹100

Total Debits = ₹100

Total Credits = ₹100

The ledger remains balanced.

Fraud and Security

- Transaction PIN validation and lockout
- Transaction limits
- Fraud detection
- Flagged transaction review
- Administrative approval and rejection
- Idempotency-key validation

Statements

Supports monthly transaction statements:

"GET /statements?month=2026-11&format=pdf"

"GET /statements?month=2026-11&format=csv"

Statements contain opening balance, transaction details, total credits, total debits, and closing balance.

Scheduled Jobs

- Withdrawal processing every 5 minutes
- Cashback processing every hour
- Ledger reconciliation daily

Ledger Reconciliation

The reconciliation process checks wallet balances against their ledger accounts and verifies total debit and credit amounts.

Manual test result — November 6, 2026

Metric| Result
Wallets checked| 5
Total debits| ₹2,980.00
Total credits| ₹2,980.00
Mismatches| 0
Result| PASSED

Run the reconciliation manually:

python -m app.jobs.reconciliation_job

Installation and Setup

1. Clone the repository

git clone <repository-url>
cd digital_wallet_system

Replace "<repository-url>" with the actual GitHub repository URL.

2. Create a virtual environment

python -m venv venv

Activate on Windows:

.\venv\Scripts\Activate.ps1

3. Install dependencies

pip install -r requirements.txt

4. Configure environment variables

Copy ".env.example" to ".env" and configure the MySQL database, JWT secret, and SMTP credentials.

Never commit ".env" or actual credentials.

5. Apply database migrations

alembic upgrade head

This assumes the project's Alembic migrations are correctly configured and committed.

6. Start the application

uvicorn app.main:app --reload

7. Open Swagger UI

http://127.0.0.1:8000/docs

API Testing

APIs were tested through Swagger UI, including authentication, wallet transactions, merchant payments, refunds, withdrawals, cashback, fraud review, and statements.

The reconciliation process was also tested using the command-line interface.

Test Accounts

Create separate test accounts for the following roles:

Role| Purpose
Admin| KYC approval, fraud review, administration
User| Wallet transfers, payments, statements
Merchant| Merchant payments, refunds, QR code

Actual test credentials should be provided separately or documented using disposable test accounts only. Never publish real passwords or secrets.

Assumptions and Known Limitations

- Payment processing is simulated; no real banking network is connected.
- Email delivery requires valid SMTP configuration.
- The scheduler runs within the application process and is intended for development/testing.
- The daily reconciliation job has been configured and tested manually.
- Full request replay behavior for idempotency has not been verified.
- Money-request workflows and reporting dashboards have not been verified as complete.
- Request-expiry and cleanup jobs have not been verified.
- Automatic Admin email alerts for reconciliation mismatches have not yet been implemented.
- Some assignment-required API routes and advanced validation rules may differ from the current implementation.

Submission Contents

- FastAPI application source code
- SQLAlchemy models and API routers
- Alembic migration files
- "requirements.txt"
- ".env.example"
- ".gitignore"
- "README.md"
- Swagger API screenshots
- PDF and CSV statement screenshots
- Ledger reconciliation screenshot

Project Status

Core wallet and payment workflows have been implemented and tested. Additional assignment requirements remain pending or require further verification.

Assignment: Digital Wallet & Payments System
Submission Date: November 6, 2026