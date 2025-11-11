import os
from typing import List, Optional, Literal, Any, Dict
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, EmailStr
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import User as UserSchema, Category as CategorySchema, Product as ProductSchema, PaymentMethod as PaymentMethodSchema, Order as OrderSchema, Rating as RatingSchema, Deposit as DepositSchema, ProviderConfig as ProviderConfigSchema

app = FastAPI(title="Vechnost API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helpers
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

def oid(s: str) -> ObjectId:
    try:
        return ObjectId(s)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id")

# Basic security (very simple for demo)
import hashlib

def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

# ---------- Basic endpoints ----------
@app.get("/")
def read_root():
    return {"name": "Vechnost", "message": "Backend running"}

@app.get("/test")
def test_database():
    info = {
        "backend": "ok",
        "database": "not-configured",
        "collections": []
    }
    try:
        if db is not None:
            info["database"] = "connected"
            info["collections"] = db.list_collection_names()
        else:
            info["database"] = "not-available"
    except Exception as e:
        info["database"] = f"error: {str(e)[:80]}"
    return info

# ---------- Auth ----------
class RegisterIn(BaseModel):
    name: str
    email: EmailStr
    password: str
    phone: Optional[str] = None

class LoginIn(BaseModel):
    email: EmailStr
    password: str

@app.post("/api/auth/register")
def register(payload: RegisterIn):
    if db["user"].find_one({"email": payload.email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    user = UserSchema(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        phone=payload.phone,
        level="member",
        is_active=True,
    )
    new_id = create_document("user", user)
    return {"id": new_id, "message": "Registered"}

@app.post("/api/auth/login")
def login(payload: LoginIn):
    user = db["user"].find_one({"email": payload.email})
    if not user or user.get("password_hash") != hash_password(payload.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    # For demo, token is user id hash; in production use JWT
    token = hashlib.sha256(str(user["_id"]).encode()).hexdigest()
    return {"token": token, "user": {"id": str(user["_id"]), "name": user.get("name"), "level": user.get("level")}}

# ---------- Admin CRUD (no auth gating for demo) ----------

# Categories
@app.post("/api/admin/categories")
def admin_create_category(cat: CategorySchema):
    new_id = create_document("category", cat)
    return {"id": new_id}

@app.get("/api/admin/categories")
@app.get("/api/categories")
def list_categories():
    items = get_documents("category")
    for it in items:
        it["id"] = str(it.pop("_id"))
    return items

@app.delete("/api/admin/categories/{category_id}")
def delete_category(category_id: str):
    res = db["category"].delete_one({"_id": oid(category_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"deleted": True}

# Products
@app.post("/api/admin/products")
def admin_create_product(prod: ProductSchema):
    new_id = create_document("product", prod)
    return {"id": new_id}

@app.get("/api/products")
def list_products(category: Optional[str] = None, q: Optional[str] = None, type: Optional[str] = None):
    filt: Dict[str, Any] = {}
    if category:
        filt["category_id"] = category
    if type:
        filt["type"] = type
    if q:
        filt["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
            {"tags": {"$regex": q, "$options": "i"}},
        ]
    items = get_documents("product", filt)
    for it in items:
        it["id"] = str(it.pop("_id"))
    return items

@app.delete("/api/admin/products/{product_id}")
def delete_product(product_id: str):
    res = db["product"].delete_one({"_id": oid(product_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"deleted": True}

# Users (admin)
@app.get("/api/admin/users")
def admin_list_users():
    items = get_documents("user")
    for it in items:
        it["id"] = str(it.pop("_id"))
        it.pop("password_hash", None)
    return items

@app.delete("/api/admin/users/{user_id}")
def admin_delete_user(user_id: str):
    res = db["user"].delete_one({"_id": oid(user_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"deleted": True}

# Payment Methods
@app.post("/api/admin/payment-methods")
def admin_create_payment_method(pm: PaymentMethodSchema):
    new_id = create_document("paymentmethod", pm)
    return {"id": new_id}

@app.get("/api/payment-methods")
def list_payment_methods():
    items = get_documents("paymentmethod", {"is_active": True})
    for it in items:
        it["id"] = str(it.pop("_id"))
    return items

@app.delete("/api/admin/payment-methods/{method_id}")
def admin_delete_payment_method(method_id: str):
    res = db["paymentmethod"].delete_one({"_id": oid(method_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"deleted": True}

# Provider Configs and bulk add from providers (mock)
@app.post("/api/admin/providers")
def admin_add_provider(cfg: ProviderConfigSchema):
    new_id = create_document("providerconfig", cfg)
    return {"id": new_id}

class BulkAddIn(BaseModel):
    provider: Literal["vip", "digiflazz"]
    items: List[dict] = Field(default_factory=list)

@app.post("/api/admin/products/bulk-add")
def admin_bulk_add_products(payload: BulkAddIn):
    if not payload.items:
        raise HTTPException(status_code=400, detail="No items provided")
    docs = []
    now = datetime.now(timezone.utc)
    for it in payload.items:
        doc = {
            "title": it.get("title") or it.get("name") or "Produk",
            "description": it.get("description"),
            "price": float(it.get("price", 0)),
            "category_id": it.get("category_id"),
            "type": it.get("type") or "game_topup",
            "provider": payload.provider,
            "is_active": True,
            "tags": it.get("tags", []),
            "created_at": now,
            "updated_at": now,
        }
        docs.append(doc)
    res = db["product"].insert_many(docs)
    return {"inserted": len(res.inserted_ids)}

# ---------- Orders, Payments, Ratings, Deposits ----------

@app.post("/api/orders")
def create_order(order: OrderSchema):
    # Price calculation
    prod = db["product"].find_one({"_id": oid(order.product_id)})
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")
    base = float(prod.get("price", 0)) * int(order.amount)
    total = base
    pm = None
    if order.payment_method_code:
        pm = db["paymentmethod"].find_one({"code": order.payment_method_code, "is_active": True})
        if pm:
            total = base + base * float(pm.get("fee_percent", 0)) / 100.0 + float(pm.get("fee_flat", 0))
    payload = order.model_dump()
    payload.update({
        "status": "pending",
        "provider": order.provider or prod.get("provider") or "manual",
        "total_price": round(total, 2),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    })
    order_id = db["order"].insert_one(payload).inserted_id

    # Mock payment URL for Tripay/Tokopay
    pay_url = None
    if pm and pm.get("gateway") in ("tripay", "tokopay"):
        pay_url = f"https://pay.mock/{pm['gateway']}/{order_id}"
        db["order"].update_one({"_id": order_id}, {"$set": {"payment_url": pay_url}})

    return {"id": str(order_id), "payment_url": pay_url, "total_price": payload["total_price"]}

@app.get("/api/orders")
def list_orders(status: Optional[str] = None, user_id: Optional[str] = None):
    filt: Dict[str, Any] = {}
    if status:
        filt["status"] = status
    if user_id:
        filt["user_id"] = user_id
    items = get_documents("order", filt)
    out = []
    for it in items:
        it["id"] = str(it.pop("_id"))
        out.append(it)
    return out

# Webhooks (mock: mark paid)
class WebhookIn(BaseModel):
    reference: Optional[str] = None
    status: Literal["paid", "failed", "pending"] = "paid"

@app.post("/api/payment/tripay/webhook")
@app.post("/api/payment/tokopay/webhook")
def payment_webhook(payload: WebhookIn, request: Request):
    ref = payload.reference or request.query_params.get("reference")
    if not ref:
        raise HTTPException(status_code=400, detail="Missing reference")
    order = db["order"].find_one({"payment_reference": ref})
    if not order:
        # allow direct id too
        try:
            order = db["order"].find_one({"_id": oid(ref)})
        except Exception:
            order = None
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    db["order"].update_one({"_id": order["_id"]}, {"$set": {"status": payload.status, "updated_at": datetime.now(timezone.utc)}})
    return {"ok": True}

# Ratings
@app.post("/api/ratings")
def create_rating(r: RatingSchema):
    # basic validation
    if not db["product"].find_one({"_id": oid(r.product_id)}):
        raise HTTPException(status_code=404, detail="Product not found")
    new_id = create_document("rating", r)
    return {"id": new_id}

@app.get("/api/ratings/{product_id}")
def list_ratings(product_id: str):
    items = get_documents("rating", {"product_id": product_id})
    for it in items:
        it["id"] = str(it.pop("_id"))
    return items

# Deposits
@app.post("/api/deposits")
def create_deposit(dep: DepositSchema):
    new_id = create_document("deposit", dep)
    return {"id": new_id}

@app.get("/api/deposits")
def list_deposits(user_id: Optional[str] = None, status: Optional[str] = None):
    filt: Dict[str, Any] = {}
    if user_id:
        filt["user_id"] = user_id
    if status:
        filt["status"] = status
    items = get_documents("deposit", filt)
    for it in items:
        it["id"] = str(it.pop("_id"))
    return items

# ---------- Tools & Top Ranking ----------
class CheckIdIn(BaseModel):
    game: str
    user_id: str
    server: Optional[str] = None

@app.post("/api/tools/check-game-id")
def check_game_id(payload: CheckIdIn):
    # Mock check; in production call provider API
    if len(payload.user_id.strip()) < 3:
        return {"valid": False, "message": "ID terlalu pendek"}
    # Fake nickname echo
    nickname = f"Player-{payload.user_id[-4:]}"
    return {"valid": True, "nickname": nickname, "game": payload.game}

class CalcIn(BaseModel):
    price: float
    amount: int = 1
    fee_percent: float = 0.0
    fee_flat: float = 0.0

@app.post("/api/tools/calc")
def calc_total(payload: CalcIn):
    base = payload.price * payload.amount
    total = base + base * payload.fee_percent / 100.0 + payload.fee_flat
    return {"base": round(base, 2), "total": round(total, 2)}

@app.get("/api/top")
def top_ranking(limit: int = 10):
    pipeline = [
        {"$group": {"_id": "$product_id", "orders": {"$sum": 1}, "revenue": {"$sum": "$total_price"}}},
        {"$sort": {"orders": -1}},
        {"$limit": limit},
    ]
    res = list(db["order"].aggregate(pipeline))
    out = []
    for r in res:
        prod = db["product"].find_one({"_id": oid(r["_id"])}) if r.get("_id") else None
        out.append({
            "product_id": r.get("_id"),
            "product_title": prod.get("title") if prod else None,
            "orders": r.get("orders", 0),
            "revenue": round(float(r.get("revenue", 0) or 0), 2),
        })
    return out

# ---------- Admin Monitoring ----------
@app.get("/api/admin/overview")
def admin_overview():
    return {
        "users": db["user"].count_documents({}),
        "products": db["product"].count_documents({}),
        "orders": db["order"].count_documents({}),
        "deposits": db["deposit"].count_documents({}),
        "pending_orders": db["order"].count_documents({"status": "pending"}),
        "paid_orders": db["order"].count_documents({"status": "paid"}),
        "recent_orders": [
            {**{k: (str(v) if k == "_id" else v) for k, v in o.items()}}
            for o in db["order"].find().sort("created_at", -1).limit(10)
        ],
    }

# Note: In a real system, secure admin routes with proper authentication & roles.

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
