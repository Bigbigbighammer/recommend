"""PyTorch YouTubeDNN recall model for online inference."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


def bucket_age(value: Any) -> str:
    try:
        age = int(value)
    except (TypeError, ValueError):
        return "unknown"
    if age <= 0:
        return "unknown"
    if age < 18:
        return "under18"
    if age < 25:
        return "18-24"
    if age < 35:
        return "25-34"
    if age < 45:
        return "35-44"
    if age < 50:
        return "45-49"
    if age < 56:
        return "50-55"
    return "56+"


class TorchYouTubeDNN(nn.Module):
    def __init__(
        self,
        num_users: int,
        num_items: int,
        gender_size: int,
        age_size: int,
        occupation_size: int,
        dim: int,
        hidden_dim: int,
        history_window: int,
    ) -> None:
        super().__init__()
        self.history_window = history_window
        self.item_embedding = nn.Embedding(num_items + 1, dim, padding_idx=0)
        self.user_embedding = nn.Embedding(num_users, dim)
        self.gender_embedding = nn.Embedding(gender_size, max(2, dim // 8))
        self.age_embedding = nn.Embedding(age_size, max(2, dim // 8))
        self.occupation_embedding = nn.Embedding(occupation_size, max(4, dim // 4))
        profile_dim = dim + max(2, dim // 8) + max(2, dim // 8) + max(4, dim // 4)
        self.user_tower = nn.Sequential(
            nn.Linear(dim + profile_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.0),
            nn.Linear(hidden_dim, dim),
        )
        self.item_bias = nn.Parameter(torch.zeros(num_items))
        weights = torch.linspace(0.6, 1.0, steps=history_window).view(1, history_window, 1)
        self.register_buffer("history_weights", weights)

    def encode_user(
        self,
        user_idx: torch.Tensor,
        gender_idx: torch.Tensor,
        age_idx: torch.Tensor,
        occupation_idx: torch.Tensor,
        hist_tokens: torch.Tensor,
    ) -> torch.Tensor:
        hist_emb = self.item_embedding(hist_tokens)
        mask = hist_tokens.ne(0).float().unsqueeze(-1)
        weights = self.history_weights * mask
        denom = weights.sum(dim=1).clamp_min(1.0)
        hist_vec = (hist_emb * weights).sum(dim=1) / denom

        profile = torch.cat([
            self.user_embedding(user_idx),
            self.gender_embedding(gender_idx),
            self.age_embedding(age_idx),
            self.occupation_embedding(occupation_idx),
        ], dim=1)
        user_vec = self.user_tower(torch.cat([hist_vec, profile], dim=1))
        return user_vec


class TorchYouTubeDNNPredictor:
    def __init__(self, checkpoint_path: str | Path, device: str = "cpu") -> None:
        self.device = torch.device(device)
        checkpoint = torch.load(checkpoint_path, map_location=self.device, weights_only=False)
        self.movie_ids = np.asarray(checkpoint["movie_ids"], dtype=np.int64)
        self.user_ids = np.asarray(checkpoint["user_ids"], dtype=np.int64)
        self.vocabs: dict[str, dict[str, int]] = checkpoint["vocabs"]
        self.dim = int(checkpoint["dim"])
        self.hidden_dim = int(checkpoint["hidden_dim"])
        self.history_window = int(checkpoint["history_window"])
        self.movie_to_idx = {int(movie_id): idx for idx, movie_id in enumerate(self.movie_ids.tolist())}
        self.user_to_idx = {int(user_id): idx for idx, user_id in enumerate(self.user_ids.tolist())}

        self.model = TorchYouTubeDNN(
            num_users=len(self.user_ids),
            num_items=len(self.movie_ids),
            gender_size=len(self.vocabs.get("gender", {"unknown": 0})),
            age_size=len(self.vocabs.get("age", {"unknown": 0})),
            occupation_size=len(self.vocabs.get("occupation", {"unknown": 0})),
            dim=self.dim,
            hidden_dim=self.hidden_dim,
            history_window=self.history_window,
        )
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.model.to(self.device)
        self.model.eval()
        with torch.no_grad():
            item_emb = self.model.item_embedding.weight[1:].detach()
            self.default_user_idx = torch.tensor([0], dtype=torch.long, device=self.device)
            self.default_vector = F.normalize(item_emb.mean(dim=0, keepdim=True), dim=1)

    def user_vector(self, user_features: dict[str, Any], hist_movie_ids: list[int]) -> list[float]:
        if not hist_movie_ids:
            vec = self.default_vector
        else:
            user_id = self._extract_user_id(user_features)
            user_idx = self.user_to_idx.get(user_id, 0)
            gender_idx = self._vocab_index("gender", user_features.get("gender"))
            age_idx = self._vocab_index("age", bucket_age(user_features.get("age")))
            occupation_idx = self._vocab_index("occupation", user_features.get("occupation"))
            hist_tokens = self._history_tokens(hist_movie_ids)
            with torch.no_grad():
                vec = self.model.encode_user(
                    torch.tensor([user_idx], dtype=torch.long, device=self.device),
                    torch.tensor([gender_idx], dtype=torch.long, device=self.device),
                    torch.tensor([age_idx], dtype=torch.long, device=self.device),
                    torch.tensor([occupation_idx], dtype=torch.long, device=self.device),
                    torch.tensor([hist_tokens], dtype=torch.long, device=self.device),
                )
                vec = F.normalize(vec, dim=1)
        values = vec.squeeze(0).detach().cpu().numpy().astype(float)
        return [float(round(v, 8)) for v in values.tolist()]

    def _history_tokens(self, hist_movie_ids: list[int]) -> list[int]:
        # Online Redis history is most-recent-first, while the model was trained
        # with chronological history and gives larger weights to later positions.
        recent = [int(v) for v in hist_movie_ids[: self.history_window]]
        chronological = list(reversed(recent))
        tokens = [
            self.movie_to_idx[movie_id] + 1
            for movie_id in chronological
            if movie_id in self.movie_to_idx
        ]
        padded = [0] * self.history_window
        if tokens:
            padded[-len(tokens):] = tokens[-self.history_window:]
        return padded

    def _vocab_index(self, name: str, value: Any) -> int:
        vocab = self.vocabs.get(name, {"unknown": 0})
        if value is None:
            return vocab.get("unknown", 0)
        return vocab.get(str(value), vocab.get("unknown", 0))

    @staticmethod
    def _extract_user_id(user_features: dict[str, Any]) -> int | None:
        value = user_features.get("userId", user_features.get("user_id"))
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
