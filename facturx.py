# app/routers/facturx.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from fastapi.responses import StreamingResponse

from app.services.facturx_service import generate_facturx_pdf  # adapte le chemin si besoin

router = APIRouter(prefix="/facturx", tags=["facturx"])


class InvoiceLine(BaseModel):
    description: str
    quantity: float
    unitPrice: float
    vatRate: float


class InvoiceRequest(BaseModel):
    invoiceNumber: str
    invoiceDate: str
    serviceDate: str
    currency: str
    sellerName: str
    sellerAddress: str
    sellerVat: str | None = ""
    buyerName: str
    buyerAddress: str
    buyerSiren: str | None = ""
    paymentTerms: str
    paymentMethod: str
    notes: str | None = ""
    lines: list[InvoiceLine]


@router.post("/generate-facturx")
async def generate_facturx_endpoint(payload: InvoiceRequest):
    try:
        pdf_bytes, filename = generate_facturx_pdf(payload.dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )