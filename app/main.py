from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.models.cashback import Cashback

from app.auth.router import router as auth_router
from app.routers.wallet import router as wallet_router
from app.routers.otp import router as otp_router
from app.routers.p2p import router as p2p_router
from app.routers.transactions import router as transactions_router
from app.routers.merchant import router as merchant_router
from app.routers.cashback import router as cashback_router
from app.routers.cashback_funding import router as cashback_funding_router
from app.routers.bank_account import router as bank_account_router
from app.routers.kyc import router as kyc_router
from app.routers.withdrawals import router as withdrawals_router
from app.jobs.scheduler import (
    start_scheduler,
    stop_scheduler
)
from app.routers.fraud_review import router as fraud_review_router
from app.routers.statement import router as statement_router
from app.routers.reports import router as reports_router
from app.routers.notifications import router as notifications_router



@asynccontextmanager
async def lifespan(app: FastAPI):
    
    start_scheduler()

    try:
        yield
    finally:
        
        stop_scheduler()




app = FastAPI(
    title="Digital Wallet & Payments System",
    description="Secure Digital Wallet API with FastAPI and MySQL",
    version="1.0.0",
    lifespan=lifespan
)




app.include_router(auth_router)
app.include_router(wallet_router)
app.include_router(otp_router)
app.include_router(p2p_router)
app.include_router(transactions_router)
app.include_router(merchant_router)
app.include_router(cashback_router)
app.include_router(cashback_funding_router)
app.include_router(bank_account_router)
app.include_router(kyc_router)
app.include_router(withdrawals_router)
app.include_router(fraud_review_router)
app.include_router(statement_router)
app.include_router(reports_router)
app.include_router(notifications_router)



@app.get("/")
def home():
    return {
        "message": "Digital Wallet System API is running successfully"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }