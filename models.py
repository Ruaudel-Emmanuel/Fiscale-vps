from typing import List, Optional
from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, EmailStr, Field, HttpUrl, constr


class OperationNature(str, Enum):
    goods = "goods"
    services = "services"
    mixed = "mixed"


class Profile(str, Enum):
    BASIC = "BASIC"
    EN16931 = "EN16931"


SIREN = constr(pattern=r"^[0-9]{9}$")
SIRET = constr(pattern=r"^[0-9]{14}$")
CountryCode = constr(pattern=r"^[A-Z]{2}$")
CurrencyCode = constr(pattern=r"^[A-Z]{3}$")


class Address(BaseModel):
    line1: str = Field(..., min_length=1)
    line2: Optional[str] = None
    postal_code: str = Field(..., min_length=1)
    city: str = Field(..., min_length=1)
    country_code: CountryCode = Field(default="FR")


class InvoiceHeader(BaseModel):
    number: str = Field(..., min_length=1)
    issue_date: date
    supply_date: Optional[date] = None
    currency: CurrencyCode = Field(default="EUR")
    operation_nature: OperationNature
    tva_on_debits_option: bool = Field(default=False)
    payment_terms: Optional[str] = None
    due_date: Optional[date] = None


class Seller(BaseModel):
    name: str = Field(..., min_length=1)
    siren: SIREN
    siret: Optional[SIRET] = None
    vat_number: Optional[str] = None
    naf_code: Optional[str] = None
    legal_form: Optional[str] = None
    share_capital: Optional[float] = None
    rcs_city: Optional[str] = None
    address: Address
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    website: Optional[HttpUrl] = None


class Buyer(BaseModel):
    name: str = Field(..., min_length=1)
    siren: SIREN
    siret: Optional[SIRET] = None
    vat_number: Optional[str] = None
    address_billing: Address
    address_shipping: Optional[Address] = None
    email: Optional[EmailStr] = None


class InvoiceLine(BaseModel):
    line_number: int = Field(..., ge=1)
    description: str = Field(..., min_length=1)
    quantity: float = Field(..., gt=0)
    unit: Optional[str] = None
    unit_price_ht: float
    tva_rate: float
    discount_rate: float = Field(default=0, ge=0, le=100)


class InvoiceTotals(BaseModel):
    total_ht: Optional[float] = None
    total_discount: Optional[float] = None
    total_tva: Optional[float] = None
    total_ttc: Optional[float] = None


class Meta(BaseModel):
    language: str = Field(default="fr")
    profile: Profile = Field(default=Profile.BASIC)
    created_at: Optional[datetime] = None
    generation_tool: Optional[str] = None


class InvoicePayload(BaseModel):
    invoice: InvoiceHeader
    seller: Seller
    buyer: Buyer
    lines: List[InvoiceLine]
    totals: Optional[InvoiceTotals] = None
    meta: Optional[Meta] = None