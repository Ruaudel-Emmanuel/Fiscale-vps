from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.facturx import router as facturx_router

app = FastAPI(
    title="Fiscale Factur-X API",
    version="3.0.0",
    description="API de génération de factures Factur-X sur VPS avec payload structuré et validations métier.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://rennesdev.fr",
        "https://www.rennesdev.fr",
        "https://fiscale.rennesdev.fr",
        "http://localhost:3000",
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "facturx-api", "version": "3.0.0"}


app.include_router(facturx_router)