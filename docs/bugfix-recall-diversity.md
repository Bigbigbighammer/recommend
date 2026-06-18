# Bugfix: Rating Display & Recall Diversity

Branch: `bugfix/rating-display-and-recall-diversity`

## Issues Fixed

### 1. Rating records limited to 10 on profile page

**Root cause:** `UserHandler.getProfile()` hardcoded `findRecentByUser(userId, 10)`.

**Fix:**
- `RatingMapper.java` — replaced `findRecentByUser(id, limit)` with `findAllByUser(id)`, removing the LIMIT clause
- `UserHandler.java` — calls new method, returns all rating records

### 2. UserPreference recall strategy did not exclude rated movies

**Root cause:** `UserPreferenceRecallStrategy` used ES genre search directly without filtering already-rated movies. This was the only recall strategy missing the `seen` exclusion set.

**Fix:**
- `UserPreferenceRecallStrategy.java` — added `histMovieIds` filter after ES search, fetching `topK * 2` then filtering and limiting to `topK`

### 3. YouTubeDNN recall used wrong item embeddings (embedding space mismatch)

**Root cause:** `YouTubeDNNRecallStrategy` called Python inference to get a user vector trained in the YouTubeDNN interaction embedding space, but Java's `ItemEmbeddingStore` performed ANN against content-based embeddings (`item_emb.npy` from `generate_embeddings.py`, encoding genres/year/ratings). The two embedding spaces were completely disjoint, making similarity scores meaningless.

**Fix:**
- Extracted YouTubeDNN-trained item embeddings from `youtube_dnn_torch.pt` checkpoint → `data/youtubednn_item_emb.npy` + `data/youtubednn_movie_ids.npy`
- `ItemEmbeddingStore.java` — supports dual embedding spaces (content-based + YouTubeDNN). New `topKYouTubeDNN()` method uses correct embeddings
- `YouTubeDNNRecallStrategy.java` — calls `topKYouTubeDNN()` instead of `topK()`
- `application.yml` — added `youtubednn-item-emb-path` and `youtubednn-movie-ids-path` config
- `.gitignore` — allowlisted the two YouTubeDNN embedding files

### 4. Recall channel diversity — ItemCF dominance and deterministic results

**Root cause:** Two problems:
- All recall strategies produced deterministic results for the same input — same history → same recommendations every refresh
- ItemCF dominated RRF fusion because many same-genre seeds each voted for the same neighbors, accumulating scores that overwhelmed other channels

**Fixes:**

#### 4a. Channel-aware fusion with guaranteed minimum slots
`RecallStage.java`:
- New `channelAwareFusion()` method replaces simple RRF merge → random sample
- Each active recall channel gets `topK / N` guaranteed slots in the fused candidate pool
- Remaining slots filled via weighted random sampling from unselected items
- Final shuffle ensures intra-channel ordering doesn't bias DeepFM ranking
- RRF merge target reduced from `topK * 3` to `topK * 2` to tighten the pool

#### 4b. Per-strategy contribution caps
`SnakeMergeUtil.java`:
- `weightedRrfMerge()` now caps each strategy's contribution to the RRF pool proportionally to its weight: `cap = max(10, topK * weight / maxWeight)`
- Prevents low-weight strategies from overwhelming the pool by volume

#### 4c. YouTubeDNN weight increase
`application.yml`:
- YouTubeDNN weight: 6.0 → 10.0

#### 4d. ItemEmbedding multi-seed recall
`ItemEmbeddingRecallStrategy.java`:
- Changed from using only the single most recent history item as seed → last 3 items
- Each seed's neighbors weighted by decay factor (1.0, 0.6, 0.36) and scores merged

#### 4e. CF history window adjustment
- `SeqCFRecallStrategy.java`: window 30 → 50

## Files Changed

| File | Change |
|---|---|
| `.gitignore` | Allowlist YouTubeDNN embedding files |
| `application.yml` | YouTubeDNN embedding paths + weight 6.0→10.0 |
| `UserHandler.java` | All ratings instead of 10 |
| `RatingMapper.java` | `findAllByUser` replaces `findRecentByUser` |
| `RecallStage.java` | Channel-aware fusion + weighted random sampling |
| `SnakeMergeUtil.java` | Per-strategy contribution caps |
| `ItemEmbeddingStore.java` | Dual embedding spaces + `topKYouTubeDNN()` |
| `YouTubeDNNRecallStrategy.java` | Use correct YouTubeDNN embeddings |
| `ItemEmbeddingRecallStrategy.java` | 3-seed recall with decay merge |
| `UserPreferenceRecallStrategy.java` | Added rated-movie exclusion |
| `SeqCFRecallStrategy.java` | History window 30→50 |
| `docker-compose.yml` | Redis port 6379→6380 (avoid host conflict) |

## Generated Data Files

- `data/youtubednn_item_emb.npy` — 3883 YouTubeDNN-trained item embeddings (64-dim, L2-normalized), extracted from `youtube_dnn_torch.pt`
- `data/youtubednn_movie_ids.npy` — corresponding movie ID array

To regenerate after retraining:
```bash
docker exec recommend-python-inference-1 python3 -c "
import torch, numpy as np
ckpt = torch.load('/app/data/youtube_dnn_torch.pt', map_location='cpu', weights_only=False)
item_emb = ckpt['model_state_dict']['item_embedding.weight'][1:].detach().cpu().numpy()
movie_ids = ckpt['movie_ids']
norms = np.linalg.norm(item_emb, axis=1, keepdims=True)
item_emb = item_emb / np.where(norms == 0, 1.0, norms)
np.save('/app/data/youtubednn_item_emb.npy', item_emb.astype(np.float64))
np.save('/app/data/youtubednn_movie_ids.npy', movie_ids.astype(np.int64))
"
```

## Results

### Channel diversity (before → after)

| Metric | Before | After |
|---|---|---|
| Active channels per request | 1-2 | 5-6 |
| YouTubeDNN contribution | 0-1/20 | 6-9/20 |
| ItemCF contribution | 18-20/20 | 3-12/20 |

### Exclusion correctness

- 3 rounds × 20 items = 60 recommendation slots → 0 rated-movie leaks (verified with 24 rated movies)

### Recommendation freshness

- Two consecutive identical requests → 38/40 unique movies (only 2 overlap)
