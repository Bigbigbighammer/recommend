import os
import random
import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Rec Model Inference Service", version="1.0.0")

# ── Model paths ────────────────────────────────────────────────────────
MODEL_WEIGHTS_DIR = Path(__file__).resolve().parent / "model_weights"
RANKING_MODEL_PATH = MODEL_WEIGHTS_DIR / "deepfm_model.pt"
RANKING_ENCODERS_PATH = MODEL_WEIGHTS_DIR / "ranking_encoders.pkl"
RANKING_FEATURE_DIMS_PATH = MODEL_WEIGHTS_DIR / "ranking_feature_dims.pkl"

# ── Lazy-loaded ranking predictor ──────────────────────────────────────
_ranking_predictor = None


def get_ranking_predictor():
    """Load DeepFM model on first use (lazy loading)."""
    global _ranking_predictor
    if _ranking_predictor is None:
        if RANKING_MODEL_PATH.exists():
            from model_ranking import RankingPredictor
            logger.info(f"Loading DeepFM ranking model from {RANKING_MODEL_PATH}")
            _ranking_predictor = RankingPredictor(
                model_path=str(RANKING_MODEL_PATH),
                encoders_path=str(RANKING_ENCODERS_PATH),
                feature_dims_path=str(RANKING_FEATURE_DIMS_PATH),
            )
            logger.info("DeepFM ranking model loaded")
        else:
            logger.warning(f"Ranking model not found at {RANKING_MODEL_PATH}, using fallback")
    return _ranking_predictor


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
    """DeepFM CTR prediction.

    Uses a trained DeepFM model if available. Falls back to random scores
    (with a warning log) if the model hasn't been trained yet.
    """
    predictor = get_ranking_predictor()
    if predictor is not None:
        try:
            results = predictor.predict(request.user_features, request.item_features)
            return [CTRPrediction(movie_id=r["movie_id"], ctr_score=r["ctr_score"]) for r in results]
        except Exception as e:
            logger.error(f"DeepFM prediction failed, falling back to random: {e}")

    # Fallback: random scores (same behavior as before model is trained)
    logger.warning("Using random CTR fallback — train the DeepFM model for real predictions")
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
