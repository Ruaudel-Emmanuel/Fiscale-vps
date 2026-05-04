from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr


class LineItem(BaseModel):
    description: str = Field(..., min_length=1)
    quantity: float = Field(..., gt=0)
    unitPrice: float = Field(..., ge=0)
    vatRate: float = Field(..., ge=0)


class FacturXPayload(BaseModel):
    sellerName: str
    sellerSiren: str
    sellerVat: Optional[str] = "FR00000000000"
    sellerEmail: Optional[EmailStr] = None
    sellerAddress: str
    buyerName: str
    buyerSiren: Optional[str] = None
    buyerVat: Optional[str] = None
    buyerAddress: str
    deliveryAddress: Optional[str] = None
    invoiceNumber: str
    invoiceDate: str
    serviceDate: Optional[str] = None
    currency: str = "EUR"
    paymentTerms: Optional[str] = "30 jours"
    paymentMethod: Optional[str] = "Virement bancaire"
    operationNature: Optional[str] = "Service"
    vatOnDebits: Optional[str] = "No"
    notes: Optional[str] = None
    lines: List[LineItem]