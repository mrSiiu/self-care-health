"""Service FastAPI – hợp đồng API ở tài liệu thiết kế, mục 2.1.

  uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.predictor import BoDuDoan

trang_thai: dict = {}


@asynccontextmanager
async def vong_doi(app: FastAPI):
    try:
        trang_thai["bo"] = BoDuDoan.tai()     # tải 1 lần lúc khởi động
    except FileNotFoundError:
        trang_thai["bo"] = None               # /health trả DOWN → Docker đánh dấu unhealthy
    yield
    trang_thai.clear()


app = FastAPI(title="self-care-health ml-service", version="1.0", lifespan=vong_doi)


class PredictRequest(BaseModel):
    evidences: list[str] = Field(..., max_length=300, examples=[["E_91", "E_53", "E_55_@_V_89"]])
    age: int = Field(..., ge=0, le=120)
    sex: Literal["M", "F"]


class DiseaseProbability(BaseModel):
    code: str
    p: float


class PredictResponse(BaseModel):
    model_version: str
    probabilities: list[DiseaseProbability]
    ignored: list[str]


def _bo() -> BoDuDoan:
    bo = trang_thai.get("bo")
    if bo is None:
        raise HTTPException(status_code=503, detail="Mô hình chưa được tải")
    return bo


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest) -> dict:
    return _bo().du_doan(req.evidences, req.age, req.sex)


@app.get("/health")
def health() -> dict:
    bo = trang_thai.get("bo")
    return {"status": "UP" if bo else "DOWN", "model_version": bo.goi.phien_ban if bo else None}


@app.get("/model-info")
def model_info() -> dict:
    return _bo().thong_tin()
