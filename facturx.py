from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, ConfigDict, field_validator

from app.services.facturx_service import generate_facturx_pdf

router = APIRouter(prefix="/facturx", tags=["facturx"])


class PartyModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str
    addressLine1: str
    postalCode: str
    city: str
    countryCode: Literal["FR"] = "FR"
    siren: str
    vatId: str | None = None
    electronicAddress: str | None = None
    electronicAddressScheme: Literal["EM", "0002", "0009"] | None = None

    @field_validator("siren")
    @classmethod
    def validate_siren(cls, value: str) -> str:
        digits = "".join(ch for ch in value if ch.isdigit())
        if len(digits) != 9:
            raise ValueError("Le SIREN doit contenir exactement 9 chiffres")
        return digits

    @field_validator("vatId")
    @classmethod
    def normalize_vat_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().upper()
        return value or None


class InvoiceProfileModel(BaseModel):
    buyerType: Literal["B2B_FR", "B2C_FR", "B2B_EU"]
    vatRegime: Literal["FR_STANDARD_20", "FR_INTERMEDIATE_10", "FR_REDUCED_55", "FR_293B"]
    paymentMethodCode: Literal["BANK_TRANSFER", "CARD", "DIRECT_DEBIT"]
    paymentTermsCode: Literal["PAYMENT_ON_RECEIPT", "NET_30"]
    latePenaltyProfile: Literal["ECB_PLUS_10", "LEGAL_RATE"]
    collectionFeeProfile: Literal["FIXED_40_EUR", "NOT_APPLICABLE"]
    discountProfile: Literal["NO_DISCOUNT", "DISCOUNT_2_PERCENT"]


class InvoiceLineModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    description: str
    quantity: float = Field(gt=0)
    unitPrice: float = Field(ge=0)
    unitCode: Literal["H87", "DAY", "HUR"]


class InvoiceRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    invoiceNumber: str
    invoiceDate: str
    serviceDate: str
    currency: Literal["EUR"] = "EUR"
    seller: PartyModel
    buyer: PartyModel
    invoiceProfile: InvoiceProfileModel
    lines: list[InvoiceLineModel]


@router.get("/health")
def facturx_health() -> dict[str, str]:
    return {"status": "ok", "service": "facturx-router"}


@router.post("/generate-facturx")
async def generate_facturx_endpoint(payload: InvoiceRequest):
    try:
        pdf_bytes, filename = generate_facturx_pdf(payload.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )