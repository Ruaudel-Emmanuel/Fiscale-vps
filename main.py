from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers.facturx import router as facturx_router

app = FastAPI(
    title="Fiscale Factur-X API",
    version="2.0.0",
    description="API de génération de factures Factur-X sur VPS"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "service": "facturx-api"}


app.include_router(facturx_router)