"""
Database Schemas for Vechnost

Each Pydantic model below represents a MongoDB collection.
Collection name is the lowercase of the class name (e.g., User -> "user").
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Literal
from datetime import datetime

# User levels: guest, member, vip, admin
class User(BaseModel):
    name: str = Field(..., description="Full name")
    email: EmailStr = Field(..., description="Email address")
    password_hash: str = Field(..., description="Hashed password")
    phone: Optional[str] = Field(None, description="Phone number")
    level: Literal["guest", "member", "vip", "admin"] = Field("member", description="User level")
    is_active: bool = Field(True, description="Whether user is active")

class Category(BaseModel):
    name: str = Field(..., description="Category name")
    slug: str = Field(..., description="URL-friendly identifier")
    description: Optional[str] = Field(None, description="Category description")
    rank: int = Field(0, description="Display order or ranking")

class Product(BaseModel):
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Base price")
    category_id: Optional[str] = Field(None, description="Related category id")
    type: Literal[
        "game_topup", "pulsa", "data", "joki_ml", "joki_roblox", "voucher", "premium_account"
    ] = Field("game_topup", description="Product type")
    provider: Optional[Literal["vip", "digiflazz", "manual"]] = Field("manual", description="Fulfillment provider")
    is_active: bool = Field(True, description="Whether product is active")
    tags: List[str] = Field(default_factory=list, description="Search tags")

class PaymentMethod(BaseModel):
    name: str = Field(..., description="Payment method name")
    code: str = Field(..., description="Unique code")
    gateway: Optional[Literal["tripay", "tokopay", "manual"]] = Field("manual", description="Payment gateway")
    fee_percent: float = Field(0.0, ge=0, description="Percent fee")
    fee_flat: float = Field(0.0, ge=0, description="Flat fee")
    is_active: bool = Field(True, description="Whether active")

class Order(BaseModel):
    user_id: Optional[str] = Field(None, description="User ID")
    product_id: str = Field(..., description="Product ID")
    amount: int = Field(1, ge=1, description="Quantity or units")
    target_id: Optional[str] = Field(None, description="Game/account target identifier")
    status: Literal["pending", "paid", "processing", "success", "failed", "refunded"] = "pending"
    provider: Optional[Literal["vip", "digiflazz", "manual"]] = None
    payment_method_code: Optional[str] = None
    payment_reference: Optional[str] = None
    payment_url: Optional[str] = None
    total_price: float = 0.0
    note: Optional[str] = None

class Rating(BaseModel):
    user_id: Optional[str] = None
    product_id: str
    stars: int = Field(5, ge=1, le=5)
    comment: Optional[str] = None

class Deposit(BaseModel):
    user_id: str
    amount: float = Field(..., ge=0)
    status: Literal["pending", "paid", "failed"] = "pending"
    method_code: Optional[str] = None
    reference: Optional[str] = None

class ProviderConfig(BaseModel):
    name: Literal["vip", "digiflazz"]
    api_key: str
    api_secret: Optional[str] = None
    active: bool = True

# Optional: basic leaderboard/top ranking entry (aggregate, can be derived from orders)
class TopRanking(BaseModel):
    product_id: str
    orders: int = 0
    revenue: float = 0.0
    last_order_at: Optional[datetime] = None
