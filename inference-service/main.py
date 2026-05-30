from fastapi import FastAPI
from pydantic import BaseModel
from typing import Any
import random

app = FastAPI(title="Rec Model Inference Service", version="1.0.0")


# ===== DTOs =====

class RankingRequest(BaseModel):
    user_features: dict[str, Any]
    item_features: list[dict[str, Any]]
    model_version: str = ""


class RecallRequest(BaseModel):
    user_features: dict[str, Any]
    hist_movie_ids: list[int]
    model_version: str = ""


class CTRPrediction(BaseModel):
    movie_id: int
    ctr_score: float


class UserVectorResponse(BaseModel):
    user_vector: list[float]
    version: str


class ModelVersion(BaseModel):
    model_type: str
    version: str
    deploy_time: str


# ===== Endpoints =====

@app.post("/api/predict/ranking", response_model=list[CTRPrediction])
def predict_ctr(request: RankingRequest):
    """DeepFM CTR 预估 —— mock 实现"""
    return [
        CTRPrediction(
            movie_id=item["movie_id"],
            ctr_score=round(random.uniform(0.01, 0.15), 4),
        )
        for item in request.item_features
    ]


@app.post("/api/predict/recall", response_model=UserVectorResponse)
def generate_user_vector(request: RecallRequest):
    """YouTubeDNN user embedding —— mock 实现"""
    return UserVectorResponse(
        user_vector=[round(random.uniform(-1.0, 1.0), 4) for _ in range(16)],
        version="v1",
    )


@app.get("/api/health")
def health():
    return {"status": "healthy", "model_version": "v1"}


@app.get("/api/version/{model_type}", response_model=ModelVersion)
def get_version(model_type: str):
    return ModelVersion(
        model_type=model_type,
        version="v1",
        deploy_time="2026-05-30T12:00:00",
    )
