from fastapi import FastAPI, APIRouter, HTTPException, Request
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI(title="SocialHub API", version="0.1.0")
api_router = APIRouter(prefix="/api")


# =========================
# Models (DB Schema)
# =========================

class User(BaseModel):
    """SocialHub user account. Maps to a Chatwoot account upon subscription."""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr
    full_name: str
    company_name: Optional[str] = None
    phone: Optional[str] = None
    role: str = "client"  # 'client' or 'admin'
    chatwoot_account_id: Optional[int] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Subscription(BaseModel):
    """Stripe-backed subscription for a User."""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    plan: str  # 'growth' | 'pro' | 'enterprise'
    status: str = "trialing"  # trialing | active | past_due | canceled
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    price_omr: float = 0.0
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MessagingQuota(BaseModel):
    """Tracks promotional message credits per user."""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    credits_total: int = 0
    credits_used: int = 0
    last_topup_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# =========================
# Request Schemas
# =========================

class LeadCapture(BaseModel):
    """Marketing lead capture from landing page (newsletter, trial, contact sales)."""
    email: EmailStr
    full_name: Optional[str] = None
    company_name: Optional[str] = None
    phone: Optional[str] = None
    source: str = "landing"  # landing | hero_cta | pricing_cta | contact_sales | credits
    plan_interest: Optional[str] = None
    locale: str = "ar"


# =========================
# Routes
# =========================

@api_router.get("/")
async def root():
    return {"service": "SocialHub API", "status": "ok", "version": "0.1.0"}


@api_router.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


@api_router.post("/leads", status_code=201)
async def capture_lead(lead: LeadCapture):
    """Capture marketing leads from the landing page CTAs."""
    doc = lead.model_dump()
    doc["id"] = str(uuid.uuid4())
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    await db.leads.insert_one(doc)
    return {"id": doc["id"], "ok": True}


@api_router.get("/leads", response_model=List[dict])
async def list_leads(limit: int = 100):
    """Internal: list captured leads (admin use)."""
    cursor = db.leads.find({}, {"_id": 0}).sort("created_at", -1).limit(limit)
    return await cursor.to_list(length=limit)


# ---- Stripe webhook (placeholder) ----
@api_router.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    """
    Placeholder Stripe webhook receiver.
    TODO: verify signature with STRIPE_WEBHOOK_SECRET, handle:
      - checkout.session.completed -> activate subscription + provision Chatwoot account
      - invoice.payment_succeeded -> mark subscription active, top up message credits
      - invoice.payment_failed -> mark past_due
      - customer.subscription.deleted -> cancel
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    event = {"received": True, "size": len(payload), "sig": bool(sig_header)}
    await db.stripe_events.insert_one({
        "id": str(uuid.uuid4()),
        "received_at": datetime.now(timezone.utc).isoformat(),
        "size": len(payload),
        "signed": bool(sig_header),
    })
    return event


# ---- Chatwoot Super Admin API (placeholder) ----
@api_router.post("/chatwoot/accounts")
async def create_chatwoot_account(user_email: str, company_name: str):
    """
    Placeholder: provisions a new Chatwoot account for the user upon subscription success.
    TODO:
      - Call POST {CHATWOOT_URL}/platform/api/v1/accounts with CHATWOOT_PLATFORM_API_KEY
      - Then POST /platform/api/v1/users to create the user in that account
      - Persist chatwoot_account_id on User
    """
    return {
        "stub": True,
        "user_email": user_email,
        "company_name": company_name,
        "message": "Chatwoot provisioning will be wired in next phase (needs CHATWOOT_URL + CHATWOOT_PLATFORM_API_KEY).",
    }


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
