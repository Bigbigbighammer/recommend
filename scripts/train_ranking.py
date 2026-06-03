"""Train a DeepFM CTR prediction model for the ranking stage.

DeepFM = FM (first-order + second-order interactions) + Deep (DNN).

Early stopping monitors val_loss with patience=3, so --epochs sets the maximum
upper bound. Typical needs: 15-30 epochs on MovieLens 1M.

Usage:
    python scripts/train_ranking.py [--data-dir PATH] [--epochs 30] [--lr 1e-3]
"""

import argparse
import os
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader

SEED = 42
torch.manual_seed(SEED)
np.random.seed(SEED)

LABEL_COL = "click"

DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "output_ranking"
MODEL_WEIGHTS_DIR = Path(__file__).resolve().parent.parent / "inference-service" / "model_weights"


def _load_feature_list(data_dir):
    """Load the ordered feature list from feature_dims.pkl, with fallback."""
    dims_path = Path(data_dir) / "ranking_feature_dims.pkl"
    if dims_path.exists():
        with open(dims_path, "rb") as f:
            dims = pickle.load(f)
        if "all_features" in dims:
            return dims["all_features"], dims.get("user_features", []), dims.get("item_features", [])
    # Fallback for legacy data without saved feature list
    uf = ["user_id", "gender", "age", "occupation", "zip_code",
          "user_avg_rating_bin", "user_rating_count_bin", "user_active_days_bin"]
    inf = ["movie_id", "genres", "is_adult", "year", "avg_rating_bin", "rating_count_bin"]
    return uf + inf, uf, inf


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ── Dataset ───────────────────────────────────────────────────────────

class RankingDataset(Dataset):
    def __init__(self, data_dict, feature_list):
        self.features = {}
        for f in feature_list:
            self.features[f] = torch.tensor(data_dict[f], dtype=torch.long)
        self.labels = torch.tensor(data_dict[LABEL_COL], dtype=torch.float32)
        # Original user_id for per-user metric grouping (not encoded)
        self.orig_user_ids = torch.tensor(
            data_dict.get("orig_user_id", data_dict.get("user_id", np.zeros(len(self.labels)))),
            dtype=torch.long,
        )

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        feats = {f: self.features[f][idx] for f in self.features}
        feats["label"] = self.labels[idx]
        feats["orig_user_id"] = self.orig_user_ids[idx]
        return feats


# ── Model ─────────────────────────────────────────────────────────────

class FeaturesLinear(nn.Module):
    """First-order (linear) part: sum of learned biases for each feature value."""

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
        """x: (batch, num_fields), each value is feature index within its field."""
        x_offset = x + x.new_tensor(self.offsets).unsqueeze(0)
        return self.fc(x_offset).sum(dim=1) + self.bias


class FeaturesEmbedding(nn.Module):
    """Embedding layer for all sparse features."""

    def __init__(self, field_dims, embed_dim):
        super().__init__()
        self.embedding = nn.Embedding(sum(field_dims), embed_dim)
        self.offsets = []
        offset = 0
        for d in field_dims:
            self.offsets.append(offset)
            offset += d

    def forward(self, x):
        """x: (batch, num_fields) → (batch, num_fields, embed_dim)."""
        x_offset = x + x.new_tensor(self.offsets).unsqueeze(0)
        return self.embedding(x_offset)


class FactorizationMachine(nn.Module):
    """FM second-order interaction: 0.5 * (sum(emb)^2 - sum(emb^2))."""

    def forward(self, x):
        """x: (batch, num_fields, embed_dim)."""
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
    """DeepFM: Factorization Machine + Deep Neural Network for CTR prediction.

    Args:
        field_dims: list of vocabulary sizes per feature field.
        embed_dim: embedding dimension (default 16).
        mlp_dims: hidden layer dimensions for the deep part.
        dropout: dropout rate.
    """

    def __init__(self, field_dims, embed_dim=16, mlp_dims=(64, 32, 16), dropout=0.2,
                 feature_names=None):
        super().__init__()
        self.field_dims = field_dims
        self.num_fields = len(field_dims)
        self.embed_dim = embed_dim
        self.feature_names = feature_names  # ordered list of feature names

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
        """x: dict of feature_name → tensor values, or a stacked tensor."""
        if isinstance(x, dict):
            # Stack features in fixed order
            keys = self.feature_names if self.feature_names else sorted(x.keys())
            x = torch.stack([x[f] for f in keys], dim=1)

        # Embeddings: (batch, num_fields, embed_dim)
        emb = self.embedding(x)

        # FM linear
        fm_linear = self.linear(x)

        # FM interaction
        fm_inter = self.fm(emb)

        # Deep
        deep_in = emb.view(emb.size(0), -1)  # flatten
        deep_out = self.mlp(deep_in)
        deep_out = self.output(deep_out)

        # Combine
        logit = fm_linear + fm_inter + deep_out
        return torch.sigmoid(logit.squeeze(-1))


# ── Training utilities ─────────────────────────────────────────────────

def train_epoch(model, loader, optimizer, criterion, device):
    model.train()
    total_loss, total_correct, total_samples = 0.0, 0, 0
    keys = model.feature_names
    for batch in loader:
        features = {f: batch[f].to(device) for f in keys}
        labels = batch["label"].to(device)

        optimizer.zero_grad()
        preds = model(features)
        loss = criterion(preds, labels)
        loss.backward()
        optimizer.step()

        total_loss += loss.item() * labels.size(0)
        total_correct += ((preds > 0.5).float() == labels).sum().item()
        total_samples += labels.size(0)

    return total_loss / total_samples, total_correct / total_samples


@torch.no_grad()
def evaluate(model, loader, criterion, device):
    model.eval()
    total_loss, total_correct, total_samples = 0.0, 0, 0
    all_preds, all_labels, all_users = [], [], []

    keys = model.feature_names
    for batch in loader:
        features = {f: batch[f].to(device) for f in keys}
        labels = batch["label"].to(device)

        preds = model(features)
        loss = criterion(preds, labels)

        total_loss += loss.item() * labels.size(0)
        total_correct += ((preds > 0.5).float() == labels).sum().item()
        total_samples += labels.size(0)

        all_preds.extend(preds.cpu().numpy().tolist())
        all_labels.extend(labels.cpu().numpy().tolist())
        all_users.extend(batch["orig_user_id"].cpu().numpy().tolist())

    return total_loss / total_samples, total_correct / total_samples, all_preds, all_labels, all_users


def compute_auc(preds, labels):
    """Compute ROC-AUC."""
    from sklearn.metrics import roc_auc_score
    return roc_auc_score(labels, preds)


def compute_gauc(preds, labels, users):
    """Group AUC: average AUC per user, weighted by user sample count."""
    from sklearn.metrics import roc_auc_score
    user_data = {}
    for u, p, l in zip(users, preds, labels):
        user_data.setdefault(u, ([], []))
        user_data[u][0].append(p)
        user_data[u][1].append(l)

    aucs, weights = [], []
    for uid, (p_list, l_list) in user_data.items():
        if len(set(l_list)) < 2:
            continue  # skip users with only one class
        try:
            aucs.append(roc_auc_score(l_list, p_list))
            weights.append(len(l_list))
        except ValueError:
            continue

    if not aucs:
        return 0.0
    return float(np.average(aucs, weights=weights))


def compute_ranking_metrics(preds, labels, users, k_list=(5, 10, 20)):
    """Compute NDCG@K, Precision@K, Recall@K, HitRate@K.

    Groups predictions by user, ranks by predicted score, evaluates against true labels.
    """
    user_data = {}
    for u, p, l in zip(users, preds, labels):
        user_data.setdefault(u, ([], []))
        user_data[u][0].append(p)
        user_data[u][1].append(int(l))

    metrics = {f"ndcg@{k}": [] for k in k_list}
    metrics.update({f"prec@{k}": [] for k in k_list})
    metrics.update({f"recall@{k}": [] for k in k_list})
    metrics.update({f"hr@{k}": [] for k in k_list})

    for uid, (p_list, l_list) in user_data.items():
        # Sort by predicted score descending
        ranked = sorted(zip(p_list, l_list), key=lambda x: x[0], reverse=True)
        ranked_labels = [r[1] for r in ranked]
        total_pos = sum(l_list)
        if total_pos == 0:
            continue

        for k in k_list:
            topk = ranked_labels[:k]
            hits = sum(topk)

            # NDCG
            dcg = sum((2 ** rel - 1) / np.log2(i + 2) for i, rel in enumerate(topk))
            ideal_topk = sorted(l_list, reverse=True)[:k]
            idcg = sum((2 ** rel - 1) / np.log2(i + 2) for i, rel in enumerate(ideal_topk))
            ndcg = dcg / idcg if idcg > 0 else 0.0

            metrics[f"ndcg@{k}"].append(ndcg)
            metrics[f"prec@{k}"].append(hits / k)
            metrics[f"recall@{k}"].append(hits / total_pos if total_pos > 0 else 0.0)
            metrics[f"hr@{k}"].append(1.0 if hits > 0 else 0.0)

    return {name: float(np.mean(vals)) if vals else 0.0 for name, vals in metrics.items()}


# ── Main ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Train DeepFM ranking model")
    parser.add_argument("--data-dir", type=str, default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--embed-dim", type=int, default=16)
    parser.add_argument("--mlp-dims", type=str, default="64,32,16")
    parser.add_argument("--dropout", type=float, default=0.2)
    parser.add_argument("--patience", type=int, default=3)
    parser.add_argument("--device", type=str, default="cpu")
    args = parser.parse_args()

    t0 = time.time()
    device = torch.device(args.device if torch.cuda.is_available() else "cpu")
    log(f"Using device: {device}")

    # Load data
    data_dir = Path(args.data_dir)
    log(f"Loading data from {data_dir}")

    train_data = dict(np.load(data_dir / "train_ranking.npz"))
    val_data = dict(np.load(data_dir / "val_ranking.npz"))
    test_data = dict(np.load(data_dir / "test_ranking.npz"))

    with open(data_dir / "ranking_feature_dims.pkl", "rb") as f:
        feature_dims = pickle.load(f)

    # Load feature list dynamically (supports multi-hot genres, etc.)
    ALL_FEATURES, USER_FEATURES, ITEM_FEATURES = _load_feature_list(data_dir)

    log(f"Train: {len(train_data[LABEL_COL]):,}  Val: {len(val_data[LABEL_COL]):,}  Test: {len(test_data[LABEL_COL]):,}")

    # Build field_dims in ALL_FEATURES order
    field_dims = [feature_dims[f] for f in ALL_FEATURES]
    log(f"Field dims: {dict(zip(ALL_FEATURES, field_dims))}")

    # Datasets
    train_ds = RankingDataset(train_data, ALL_FEATURES)
    val_ds = RankingDataset(val_data, ALL_FEATURES)
    test_ds = RankingDataset(test_data, ALL_FEATURES)

    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size * 2, shuffle=False, num_workers=0)
    test_loader = DataLoader(test_ds, batch_size=args.batch_size * 2, shuffle=False, num_workers=0)

    # Model
    mlp_dims = tuple(int(x.strip()) for x in args.mlp_dims.split(","))
    model = DeepFM(field_dims, embed_dim=args.embed_dim, mlp_dims=mlp_dims, dropout=args.dropout,
                   feature_names=ALL_FEATURES).to(device)
    total_params = sum(p.numel() for p in model.parameters())
    log(f"DeepFM params: {total_params:,}")

    criterion = nn.BCELoss()
    optimizer = optim.Adam(model.parameters(), lr=args.lr, weight_decay=1e-5)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode="min", factor=0.5, patience=2)

    best_val_loss = float("inf")
    best_epoch = 0
    patience_counter = 0

    for epoch in range(1, args.epochs + 1):
        train_loss, train_acc = train_epoch(model, train_loader, optimizer, criterion, device)
        val_loss, val_acc, val_preds, val_labels, val_users = evaluate(model, val_loader, criterion, device)

        # Compute AUC metrics
        val_auc = compute_auc(val_preds, val_labels)
        val_gauc = compute_gauc(val_preds, val_labels, val_users)

        scheduler.step(val_loss)

        log(f"Epoch {epoch:3d} | "
            f"train_loss={train_loss:.4f} acc={train_acc:.4f} | "
            f"val_loss={val_loss:.4f} acc={val_acc:.4f} "
            f"AUC={val_auc:.4f} GAUC={val_gauc:.4f}")

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_epoch = epoch
            patience_counter = 0
            # Save best model
            os.makedirs(MODEL_WEIGHTS_DIR, exist_ok=True)
            save_path = MODEL_WEIGHTS_DIR / "deepfm_model.pt"
            torch.save({
                "model_state_dict": model.state_dict(),
                "field_dims": field_dims,
                "embed_dim": args.embed_dim,
                "mlp_dims": mlp_dims,
                "dropout": args.dropout,
                "feature_names": list(ALL_FEATURES),
                "user_features": list(USER_FEATURES),
                "item_features": list(ITEM_FEATURES),
            }, save_path)
            log(f"  Saved best model → {save_path}")
        else:
            patience_counter += 1
            if patience_counter >= args.patience:
                log(f"Early stopping at epoch {epoch}")
                break

    # Load best model for test evaluation
    checkpoint = torch.load(MODEL_WEIGHTS_DIR / "deepfm_model.pt", map_location=device, weights_only=False)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device)

    test_loss, test_acc, test_preds, test_labels, test_users = evaluate(model, test_loader, criterion, device)
    test_auc = compute_auc(test_preds, test_labels)
    test_gauc = compute_gauc(test_preds, test_labels, test_users)
    ranking_metrics = compute_ranking_metrics(test_preds, test_labels, test_users)

    log("=" * 60)
    log(f"Test Results (best epoch={best_epoch}):")
    log(f"  Loss={test_loss:.4f}  Acc={test_acc:.4f}  AUC={test_auc:.4f}  GAUC={test_gauc:.4f}")
    for name, val in sorted(ranking_metrics.items()):
        log(f"  {name}={val:.4f}")

    log(f"DONE in {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()
