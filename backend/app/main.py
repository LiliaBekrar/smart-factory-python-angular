from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .db import SessionLocal
from .models import Machine, WorkOrder

app = FastAPI(title="Smart Factory API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], allow_credentials=True
)

@app.get("/health")
def health():
    return {"status": "ok"}

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/machines")
def list_machines(db: Session = Depends(get_db)):
    return db.query(Machine).all()

@app.get("/work_orders")
def list_work_orders(db: Session = Depends(get_db)):
    return db.query(WorkOrder).all()
