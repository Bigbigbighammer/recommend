"""DeepFM ranking model for inference.

Loads a trained DeepFM model and provides CTR prediction.
Feature encoding mirrors the preprocessing in scripts/preprocess_ranking.py.
"""

import pickle
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn


# ── Model definition (mirrors train_ranking.py) ────────────────────────

class FeaturesLinear(nn.Module):
    def __init__(self, field_dims):
        super().__init__()
        self.fc = nn.Embedding(sum(field_dims), 1)
        self.bias = nn.Parameter(torch.zeros(1))
        offset = 0
        self.offsets = []
        for d in field_dims:
            self.offsets.append(offset)
            offset += d

    def forward(self, x):
        x_offset = x + x.new_tensor(self.offsets).unsqueeze(0)
        return self.fc(x_offset).sum(dim=1) + self.bias


class FeaturesEmbedding(nn.Module):
    def __init__(self, field_dims, embed_dim):
        super().__init__()
        self.embedding = nn.Embedding(sum(field_dims), embed_dim)
        self.offsets = []
        offset = 0
        for d in field_dims:
            self.offsets.append(offset)
            offset += d

    def forward(self, x):
        x_offset = x + x.new_tensor(self.offsets).unsqueeze(0)
        return self.embedding(x_offset)


class FactorizationMachine(nn.Module):
    def forward(self, x):
        sum_square = x.sum(dim=1).pow(2)
        square_sum = x.pow(2).sum(dim=1)
        return 0.5 * (sum_square - square_sum).sum(dim=1, keepdim=True)


class MultiLayerPerceptron(nn.Module):
    def __init__(self, input_dim, hidden_dims, dropout=0.2):
        super().__init__()
        layers = []
        for h in hidden_dims:
            layers.append(nn.Linear(input_dim, h))
            layers.append(nn.BatchNorm1d(h))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(dropout))
            input_dim = h
        self.mlp = nn.Sequential(*layers)

    def forward(self, x):
        return self.mlp(x)


class DeepFM(nn.Module):
    def __init__(self, field_dims, embed_dim=16, mlp_dims=(64, 32, 16), dropout=0.2,
                 feature_names=None):
        super().__init__()
        self.field_dims = field_dims
        self.num_fields = len(field_dims)
        self.embed_dim = embed_dim
        self.feature_names = feature_names

        self.linear = FeaturesLinear(field_dims)
        self.embedding = FeaturesEmbedding(field_dims, embed_dim)
        self.fm = FactorizationMachine()
        self.mlp = MultiLayerPerceptron(
            input_dim=self.num_fields * embed_dim,
            hidden_dims=mlp_dims,
            dropout=dropout,
        )
        self.output = nn.Linear(mlp_dims[-1] if mlp_dims else self.num_fields * embed_dim, 1)

    def forward(self, x):
        emb = self.embedding(x)
        fm_linear = self.linear(x)
        fm_inter = self.fm(emb)
        deep_in = emb.view(emb.size(0), -1)
        deep_out = self.mlp(deep_in)
        deep_out = self.output(deep_out)
        logit = fm_linear + fm_inter + deep_out
        return torch.sigmoid(logit.squeeze(-1))


# ── Ranking predictor ─────────────────────────────────────────────────

class RankingPredictor:
    """Loads a trained DeepFM model and serves CTR predictions."""

    def __init__(self, model_path: str, encoders_path: str, feature_dims_path: str, device: str = "cpu"):
        self.device = torch.device(device)

        # Load encoders
        with open(encoders_path, "rb") as f:
            self.encoders = pickle.load(f)

        with open(feature_dims_path, "rb") as f:
            self.feature_dims = pickle.load(f)

        # Load model
        checkpoint = torch.load(model_path, map_location=self.device, weights_only=False)

        # Use feature names from checkpoint (supports dynamic features like multi-hot genres)
        self.feature_names = checkpoint.get("feature_names")
        if self.feature_names is None:
            # Fallback for legacy checkpoints
            self.feature_names = ["user_id", "gender", "age", "occupation", "zip_code",
                                  "user_avg_rating_bin", "user_rating_count_bin",
                                  "user_active_days_bin",
                                  "movie_id", "genres", "is_adult", "year", "avg_rating_bin",
                                  "rating_count_bin"]

        self.model = DeepFM(
            field_dims=checkpoint["field_dims"],
            embed_dim=checkpoint.get("embed_dim", 16),
            mlp_dims=checkpoint.get("mlp_dims", (64, 32, 16)),
            dropout=checkpoint.get("dropout", 0.2),
            feature_names=self.feature_names,
        )
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.model.to(self.device)
        self.model.eval()

    def _bin_value(self, name: str, raw_value) -> str:
        """Bin a raw numerical value to match the LabelEncoder's training classes."""
        if raw_value is None:
            return "Unknown"

        if name in ("year",):
            y = int(raw_value) if raw_value else 0
            if y == 0:
                return "Unknown"
            if y < 1950:
                return "pre-1950"
            return f"{(y // 10) * 10}s"

        if name in ("avg_rating_bin", "user_avg_rating_bin"):
            v = float(raw_value) if raw_value else 0.0
            if v <= 0:
                return "Unknown"
            return f"{round(v * 2) / 2:.1f}"

        if name in ("rating_count_bin", "user_rating_count_bin"):
            v = int(raw_value) if raw_value else 0
            if v < 0:
                return "Unknown"
            if v == 0:
                return "0"
            if v <= 5:
                return "1-5"
            if v <= 20:
                return "6-20"
            if v <= 50:
                return "21-50"
            if v <= 100:
                return "51-100"
            if v <= 200:
                return "101-200"
            if v <= 500:
                return "201-500"
            return "501+"

        if name == "user_active_days_bin":
            v = int(raw_value) if raw_value else 0
            if v < 0:
                return "Unknown"
            if v == 0:
                return "0"
            if v <= 7:
                return "1-7"
            if v <= 30:
                return "8-30"
            if v <= 90:
                return "31-90"
            if v <= 180:
                return "91-180"
            if v <= 365:
                return "181-365"
            return "365+"

        if name == "rating_deviation_bin":
            v = float(raw_value) if raw_value else 0.0
            return f"{round(v * 2) / 2:.1f}"

        if name == "imdb_votes_bin":
            v = int(raw_value) if raw_value else 0
            if v <= 0:
                return "Unknown"
            if v <= 100:
                return "1-100"
            if v <= 1000:
                return "101-1K"
            if v <= 10000:
                return "1K-10K"
            if v <= 100000:
                return "10K-100K"
            if v <= 500000:
                return "100K-500K"
            return "500K+"

        return str(raw_value)

    def _encode_feature(self, name: str, raw_value) -> int:
        """Encode a single feature value using the saved LabelEncoder."""
        le = self.encoders.get(name)
        if le is None:
            return 0
        val_str = str(raw_value) if raw_value is not None else "Unknown"
        try:
            return int(le.transform([val_str])[0])
        except ValueError:
            return 0  # unknown → 0

    def predict(self, user_features: dict, item_features_list: list[dict]) -> list[dict]:
        """Predict CTR for a list of candidate items given user features.

        Args:
            user_features: dict with keys like userId, gender, age, occupation, zipCode
            item_features_list: list of dicts, each with keys movie_id, genres, isAdult

        Returns:
            list of dicts: [{"movie_id": int, "ctr_score": float}, ...]
        """
        if not item_features_list:
            return []

        # Map Java-side field names → Python-side field names
        user_map = {
            "userId": "user_id",
            "gender": "gender",
            "age": "age",
            "occupation": "occupation",
            "zipCode": "zip_code",
            "userAvgRating": "user_avg_rating_bin",
            "userRatingCount": "user_rating_count_bin",
            "userActiveDays": "user_active_days_bin",
        }

        item_map = {
            "movie_id": "movie_id",
            "genres": "genres",
            "isAdult": "is_adult",
            "year": "year",
            "avgRating": "avg_rating_bin",
            "ratingCount": "rating_count_bin",
            "ratingDeviation": "rating_deviation_bin",
            "imdbRating": "imdb_rating_bin",
            "imdbVotes": "imdb_votes_bin",
        }

        # Fields that are user-level (same value for all items in batch)
        user_field_names = set(self.feature_dims.get("user_features",
            ["user_id", "gender", "age", "occupation", "zip_code"]))

        # Build batch
        batch_size = len(item_features_list)
        feature_tensors = []

        for feat_name in self.feature_names:
            values = []
            for i in range(batch_size):
                if feat_name in user_field_names:
                    # User features: same value for all items
                    py_name = user_map.get(feat_name, feat_name)
                    raw = user_features.get(feat_name, user_features.get(py_name))
                else:
                    # Item features: per-item
                    item = item_features_list[i]
                    py_name = item_map.get(feat_name, feat_name)
                    raw = item.get(feat_name, item.get(py_name))

                # Apply binning for numerical features before LabelEncoder lookup
                binned = self._bin_value(feat_name, raw)
                values.append(self._encode_feature(feat_name, binned))

            feature_tensors.append(torch.tensor(values, dtype=torch.long, device=self.device))

        # Stack: (batch, num_fields)
        x = torch.stack(feature_tensors, dim=1)

        with torch.no_grad():
            scores = self.model(x).cpu().numpy().tolist()

        return [
            {"movie_id": item_features_list[i].get("movie_id", 0), "ctr_score": round(float(scores[i]), 4)}
            for i in range(batch_size)
        ]
