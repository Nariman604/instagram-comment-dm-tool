import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from database import engine, Base
from routes import webhook, api, dashboard

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(title="Instagram Comment-to-DM Tool", version="1.0.0")


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)


app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(dashboard.router)
app.include_router(webhook.router)
app.include_router(api.router)
