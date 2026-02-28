from fastapi import FastAPI

from app.api.stats import router as stats_router
from app.storage.database import Base, engine

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Lotto Game API")
app.include_router(stats_router)
