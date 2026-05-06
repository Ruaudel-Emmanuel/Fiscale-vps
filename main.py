from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.facturx import router as facturx_router


app = FastAPI(
    title="Fiscale Factur-X API",
    version="2.0.0",
    description="API de génération de factures Factur-X sur VPS",
)

# À resserrer plus tard sur tes domaines réels (ex. https://fiscale.rennesdev.fr)
origins = ["https://rennesdev.fr"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://rennesdev.fr"],
    allow_credentials=True,  # ou False si tu n'utilises pas de cookies
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "service": "facturx-api", "version": "2.0.0"}


app.include_router(facturx_router)