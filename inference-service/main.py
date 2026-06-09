import os
import random
import logging
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import numpy as np


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


# ===== YouTubeDNN recall tower =====

class YouTubeDNNModel:
    def __init__(self) -> None:
        data_dir = Path(os.environ.get("YOUTUBE_DNN_DATA_DIR", "/app/data"))
        self.torch_model_path = Path(os.environ.get("YOUTUBE_DNN_TORCH_MODEL_PATH", data_dir / "youtube_dnn_torch.pt"))
        self.item_emb_path = Path(os.environ.get("YOUTUBE_DNN_ITEM_EMB_PATH", data_dir / "item_emb.npy"))
        self.movie_ids_path = Path(os.environ.get("YOUTUBE_DNN_MOVIE_IDS_PATH", data_dir / "movie_ids.npy"))
        self.user_item_emb_path = Path(os.environ.get("YOUTUBE_DNN_USER_ITEM_EMB_PATH", data_dir / "youtube_user_item_emb.npy"))
        self.meta_path = Path(os.environ.get("YOUTUBE_DNN_META_PATH", data_dir / "youtubednn_meta.json"))
        self.history_window = int(os.environ.get("YOUTUBE_DNN_HISTORY_WINDOW", "20"))
        self.version = "unavailable"
        self.torch_predictor = None
        self.item_emb: np.ndarray | None = None
        self.user_item_emb: np.ndarray | None = None
        self.movie_to_idx: dict[int, int] = {}
        self.default_vector: np.ndarray | None = None
        self.load()

    def load(self) -> None:
        try:
            if self.torch_model_path.exists():
                from model_youtube_dnn import TorchYouTubeDNNPredictor
                self.torch_predictor = TorchYouTubeDNNPredictor(self.torch_model_path)
                self.history_window = self.torch_predictor.history_window
                self.version = "youtube-torch-v1"
                logger.info(
                    "Loaded PyTorch YouTubeDNN model: items=%s users=%s dim=%s path=%s",
                    len(self.torch_predictor.movie_ids),
                    len(self.torch_predictor.user_ids),
                    self.torch_predictor.dim,
                    self.torch_model_path,
                )
                return

            if not self.item_emb_path.exists() or not self.movie_ids_path.exists():
                logger.warning("YouTubeDNN artifacts not found; recall endpoint will use deterministic fallback.")
                return

            item_emb = np.load(self.item_emb_path).astype(np.float64)
            movie_ids = np.load(self.movie_ids_path).astype(np.int64)
            if self.user_item_emb_path.exists():
                user_item_emb = np.load(self.user_item_emb_path).astype(np.float64)
            else:
                user_item_emb = item_emb.copy()

            if len(item_emb) != len(movie_ids) or len(user_item_emb) != len(movie_ids):
                raise ValueError("embedding/movie id count mismatch")

            self.item_emb = normalize_rows(item_emb)
            self.user_item_emb = normalize_rows(user_item_emb)
            self.movie_to_idx = {int(movie_id): idx for idx, movie_id in enumerate(movie_ids.tolist())}
            self.default_vector = normalize_vector(self.user_item_emb.mean(axis=0))

            if self.meta_path.exists():
                with self.meta_path.open("r", encoding="utf-8") as f:
                    meta = json.load(f)
                self.version = str(meta.get("version", "youtube-numpy-v1"))
            else:
                self.version = "youtube-numpy-v1"

            logger.info(
                "Loaded NumPy YouTubeDNN artifacts: items=%s dim=%s version=%s",
                len(movie_ids),
                self.item_emb.shape[1],
                self.version,
            )
        except Exception as exc:
            logger.exception("Failed to load YouTubeDNN artifacts: %s", exc)
            self.torch_predictor = None
            self.item_emb = None
            self.user_item_emb = None
            self.movie_to_idx = {}
            self.default_vector = None
            self.version = "unavailable"

    def is_loaded(self) -> bool:
        return self.torch_predictor is not None or (self.user_item_emb is not None and bool(self.movie_to_idx))

    def user_vector(self, user_features: dict[str, Any], hist_movie_ids: list[int]) -> list[float]:
        if self.torch_predictor is not None:
            return self.torch_predictor.user_vector(user_features, hist_movie_ids)

        if not self.is_loaded():
            return deterministic_fallback_vector(hist_movie_ids, 16)

        assert self.user_item_emb is not None
        hist_idx = [
            self.movie_to_idx[int(movie_id)]
            for movie_id in hist_movie_ids[: self.history_window]
            if int(movie_id) in self.movie_to_idx
        ]

        if hist_idx:
            weights = np.linspace(1.0, 0.6, num=len(hist_idx), dtype=np.float64)
            vec = np.average(self.user_item_emb[hist_idx], axis=0, weights=weights)
            vec = normalize_vector(vec)
        else:
            vec = self.default_vector

        if vec is None:
            return deterministic_fallback_vector(hist_movie_ids, self.user_item_emb.shape[1])
        return [float(round(v, 8)) for v in vec.tolist()]


def normalize_rows(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.where(norms == 0.0, 1.0, norms)


def normalize_vector(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm == 0.0:
        return vector
    return vector / norm


def deterministic_fallback_vector(hist_movie_ids: list[int], dim: int) -> list[float]:
    seed = sum(int(v) * 131 for v in hist_movie_ids[-20:]) or 2026
    rng = random.Random(seed)
    values = [rng.uniform(-1.0, 1.0) for _ in range(dim)]
    norm = sum(v * v for v in values) ** 0.5 or 1.0
    return [round(v / norm, 8) for v in values]


youtube_model = YouTubeDNNModel()


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
    """YouTubeDNN user embedding generated from trained recall artifacts."""
    return UserVectorResponse(
        user_vector=youtube_model.user_vector(request.user_features, request.hist_movie_ids),
        version=youtube_model.version,
    )


@app.get("/api/health")
def health():
    return {
        "status": "healthy",
        "model_version": youtube_model.version,
        "recall_model_loaded": youtube_model.is_loaded(),
        "recall_model_type": "torch" if youtube_model.torch_predictor is not None else "numpy_or_fallback",
    }


@app.get("/api/version/{model_type}", response_model=ModelVersion)
def get_version(model_type: str):
    return ModelVersion(
        model_type=model_type,
        version=youtube_model.version if model_type == "recall" else "v1",
        deploy_time="2026-05-30T12:00:00",
    )
