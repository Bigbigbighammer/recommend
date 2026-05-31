# Rec 推荐系统架构文档

## 一、在线流程与离线模型交互

在线服务（Java）通过 HTTP RPC 调用离线推理服务（Python），负责特征工程、召回、排序、重排。离线模型负责模型推理（向量生成 / CTR 预估）。

### 1.1 召回阶段 (Recall)

**在线 → 离线**：`POST /api/predict/recall`

```json
// RecallRequest (序列化为 snake_case)
{
  "user_features": {
    "userId": 1,           // Long
    "gender": "F",         // String
    "age": "Under 18",     // String
    "occupation": "K-12 student",  // String
    "zipCode": "48067"     // String
  },
  "hist_movie_ids": [6, 32, 47, 1566],  // 用户历史观看的电影 ID 列表
  "model_version": ""      // 模型版本 (当前未使用)
}
```

**离线 → 在线**：JSON → `UserVectorResponse`

```json
{
  "user_vector": [0.12, -0.34, ..., 0.78],  // 16 维 float 数组 (与 item_emb.npy 维度一致)
  "version": "v1"
}
```

**在线后续处理**：用户向量与 `ItemEmbeddingStore` 中预加载的 `item_emb.npy` (3883 × 16) 做点积，取 Top-K。

### 1.2 排序阶段 (Ranking)

**在线 → 离线**：`POST /api/predict/ranking`

```json
// RankingRequest (序列化为 snake_case)
{
  "user_features": {
    "userId": 1,
    "gender": "F",
    "age": "Under 18",
    "occupation": "K-12 student",
    "zipCode": "48067",
    "histMovieIds": [6, 32, 47],    // 来自 Redis + 前端
    "preferredGenres": ["Action","Drama"]  // 来自 Redis
  },
  "item_features": [
    { "movie_id": 6, "genres": "Action", "isAdult": 0 },
    { "movie_id": 32, "genres": "Drama", "isAdult": 0 }
  ],
  "model_version": ""
}
```

**注意**：当前只传 `movie_id`、`genres`（首类型字符串）、`isAdult` 三个物品特征。真实 DeepFM 模型需要完整特征编码（所有用户侧 + 物品侧特征列），应该在离线推理服务内部用 LabelEncoder 编码，或由 Java 侧预编码后传递。

**离线 → 在线**：JSON → `List<CTRPrediction>`

```json
[
  { "movie_id": 6,  "ctr_score": 0.0823 },
  { "movie_id": 32, "ctr_score": 0.0651 }
]
```

**在线后续处理**：按 `ctr_score` 降序排列候选集，取 Top-N。

---

## 二、存储架构

### 2.1 PostgreSQL (主数据库)

**地址**：`postgres:5432`，库名 `rec_db`

```
┌─────────────────────────────────────────────────────────────┐
│                         users                               │
├─────────────┬───────────────────────────────────────────────┤
│ user_id     │ SERIAL PK                                     │
│ email       │ VARCHAR(255) UNIQUE                           │
│ username    │ VARCHAR(100) UNIQUE                           │
│ hashed_password │ VARCHAR(255)     ← 明文存储 (MVP)          │
│ is_active   │ SMALLINT DEFAULT 1                            │
│ is_superuser│ SMALLINT DEFAULT 0                            │
│ gender      │ CHAR(1)             ← "M" / "F" / "O"         │
│ age         │ VARCHAR(20)         ← "Under 18" / "25-34" ..│
│ occupation  │ VARCHAR(100)                                 │
│ zip_code    │ VARCHAR(10)                                   │
│ created_at  │ TIMESTAMP                                     │
│ preferred_genres │ TEXT[]         ← {"Action","Drama"}      │
└─────────────┴───────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                        movies                               │
├──────────────┬──────────────────────────────────────────────┤
│ movie_id     │ SERIAL PK                                    │
│ imdb_id      │ VARCHAR(20) UNIQUE    ← tt0114746             │
│ title        │ VARCHAR(255)                                 │
│ year         │ INTEGER                                      │
│ genres       │ TEXT[]               ← {"Drama","Sci-Fi"}    │
│ description  │ TEXT                                         │
│ avg_rating   │ FLOAT                ← 在线实时重算            │
│ rating_count │ INTEGER DEFAULT 0                            │
│ imdb_rating  │ FLOAT                ← IMDb 导入              │
│ imdb_votes   │ INTEGER                                      │
│ title_type   │ VARCHAR(50)          ← "movie"               │
│ runtime_minutes│ INTEGER                                    │
│ poster_url   │ VARCHAR(500)         ← "/posters/32.png"     │
│ is_adult     │ SMALLINT DEFAULT 0                           │
│ created_by   │ INTEGER → users(user_id)                     │
└──────────────┴──────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                       ratings                               │
├──────────┬──────────────────────────────────────────────────┤
│ user_id  │ INTEGER → users(user_id)    (PK)                  │
│ movie_id │ INTEGER → movies(movie_id)  (PK)                  │
│ rating   │ INTEGER CHECK(1..10)                              │
│ timestamp│ BIGINT                   ← epoch millis           │
└──────────┴──────────────────────────────────────────────────┘

┌──────────┬──────────────────┐
│  genres  │                  │
├──────────┼──────────────────┤
│ id       │ SERIAL PK        │
│ name     │ VARCHAR(50) UNIQUE│
└──────────┴──────────────────┘

┌─────────────────────────────────┐
│ title_ratings (IMDb)           │
├──────────────┬──────────────────┤
│ tconst       │ VARCHAR(20) PK   │
│ average_rating│ FLOAT           │
│ num_votes    │ INTEGER          │
└──────────────┴──────────────────┘

┌────────────────────────────────────────┐
│ name_basics (IMDb 人物)                │
├──────────────┬─────────────────────────┤
│ nconst       │ VARCHAR(20) PK          │
│ primary_name │ VARCHAR(255)            │
│ birth_year   │ INTEGER                 │
│ primary_profession│ TEXT[]             │
│ known_for_titles  │ TEXT[]             │
└──────────────┴─────────────────────────┘

┌──────────────────────────────────────┐
│ title_crew (IMDb 剧组)               │
├──────────┬───────────────────────────┤
│ tconst   │ VARCHAR(20) PK            │
│ directors│ TEXT[]   ← ["nm0001",...]  │
│ writers  │ TEXT[]                     │
└──────────┴───────────────────────────┘

┌───────────────────────────────────────────────┐
│ title_principals (IMDb 演员)                  │
├──────────┬────────────────────────────────────┤
│ tconst   │ VARCHAR(20)  (PK)                  │
│ ordering │ INTEGER      (PK)                  │
│ nconst   │ VARCHAR(20)                        │
│ category │ VARCHAR(50)  ← "actor"/"actress"   │
│ characters│ TEXT                              │
└──────────┴────────────────────────────────────┘
```

### 2.2 Redis

**地址**：`redis:6379`，DB 0

```
┌──────────────────────────────────────────────────────┐
│ Key                 │ Type  │ Value / Fields         │
├─────────────────────┼───────┼────────────────────────┤
│ user:{id}:history   │ LIST  │ [movieId, movieId, ...]│
│                     │       │ ← 左进，保留最近 100 条  │
├─────────────────────┼───────┼────────────────────────┤
│ user:{id}:profile   │ HASH  │ gender = "F"           │
│                     │       │ age = "Under 18"       │
│                     │       │ occupation = "..."     │
│                     │       │ zipCode = "48067"      │
│                     │       │ preferredGenres =      │
│                     │       │   "Action,Drama"       │
├─────────────────────┼───────┼────────────────────────┤
│ user:{id}:genre_ucb │ HASH  │ Action:n = 5           │
│                     │       │ Action:reward = 32     │
│                     │       │ Drama:n = 3            │
│                     │       │ Drama:reward = 18      │
│                     │       │ ← UCB 多臂老虎机统计    │
└─────────────────────┴───────┴────────────────────────┘
```

**写入时机**：
- `history`：每次评分/重评分 push（`POST /api/ratings`）
- `profile`：注册时写入（`POST /api/auth/signup`）
- `genre_ucb`：评分时 `n++` + `reward += rating`；删评分时反向递减

### 2.3 Elasticsearch

**地址**：`elasticsearch:9200`，索引 `movies`

```json
{
  "movieId":     { "type": "long" },
  "title":       { "type": "text", "fields": { "keyword": { "type": "keyword" } } },
  "year":        { "type": "integer" },
  "genres":      { "type": "keyword" },        // 多值 keyword 数组
  "description": { "type": "text" },
  "avgRating":   { "type": "float" },          // 用于过滤 avgRating >= 5
  "ratingCount": { "type": "integer" },
  "imdbRating":  { "type": "float" },
  "imdbVotes":   { "type": "integer" }
}
```

**用途**：
- 关键词搜索（`searchByKeyword`）：title / description 全文匹配
- 类型搜索（`searchByGenres`）：genres keyword 精准匹配 + avgRating >= 5 过滤
- 冷启动推荐：PreferredGenreStrategy / UCBGenreStrategy 通过类型搜索取候选集
- 自动补全（`suggest`）：title 前缀匹配

### 2.4 NPY 文件（离线产出）

| 文件 | 路径 | 内容 |
|------|------|------|
| `item_emb.npy` | `/app/data/item_emb.npy` | float64, (N, 16) — 物品 Embedding 矩阵 |
| `movie_ids.npy` | `/app/data/movie_ids.npy` | int64, (N,) — 与 embedding 行对应的电影 ID |

加载后：`Map<Long, double[]>` (movieId → 16维向量)，启动时 L2 归一化。

---

## 三、推荐管线总览

```
POST /api/recommendations/recommend
         │
         ▼
┌─────────────────────────────────────────────┐
│ 1. UserFeatureEnrichmentStage               │
│    Redis user:{id}:profile → 写入 features   │
│    Redis user:{id}:history → histMovieIds    │
│    (Redis 空时 fallback DB)                  │
├─────────────────────────────────────────────┤
│ 2. ColdStartDetectionStage                  │
│    histMovieIds.size() < 5 → isColdStart     │
├──────────────┬──────────────────────────────┤
│              │                               │
│  冷启动      │             温暖用户           │
│              ▼                               ▼
│  ┌────────────────────┐    ┌─────────────────────────┐
│  │ 3a. ColdStartPipeline│  │ 3b. RecallStage          │
│  │                      │    │                          │
│  │ UCBGenre (weight=70) │    │ YouTubeDNN → RPC 取用户向量│
│  │  Redis UCB 统计       │    │              + dot items │
│  │  → ES searchByGenres │    │ ItemEmbedding → 本地点积  │
│  │                      │    │  (最后看过的电影)         │
│  │ PreferredGenre (w=10)│    │ UserPreference → ES 搜索  │
│  │  preferredGenres     │    │                          │
│  │  → ES searchByGenres │    │ → SnakeMerge 合并        │
│  │                      │    └──────────┬──────────────┘
│  │ PopularRecent (w=20) │               │
│  │  → ES avgRating >= 5 │               ▼
│  │                      │    ┌─────────────────────────┐
│  │ → roundRobinMerge    │    │ 4. RankingStage          │
│  └──────────┬───────────┘    │    DeepFM → RPC 取 CTR   │
│             │                │    Fallback → 召回分数排序 │
│             ▼                └──────────┬──────────────┘
│  ┌────────────────────┐                │
│  │ 直接输出 (跳过精排)  │               ▼
│  └────────────────────┘    ┌─────────────────────────┐
│                            │ 5. RerankingStage        │
│                            │    GenreDispersion (max=2)│
│                            │    DecadeDispersion (max=3)│
│                            └──────────┬──────────────┘
│                                       │
              └──────────────────────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │ 6. 构建响应           │
              │    查询 movies 表     │
              │    填充 title/genres/ │
              │    posterUrl         │
              └─────────────────────┘
```

---

## 四、关键配置

```yaml
# application.yml (关键项)
recommend:
  embedding:
    item-emb-path: /app/data/item_emb.npy     # 物品 Embedding 矩阵
    movie-ids-path: /app/data/movie_ids.npy   # 对应电影 ID
  rpc:
    client: http
    inference:
      base-url: http://python-inference:8081  # 离线推理服务地址
    strategy:
      recall:
        youtubednn.enabled: true
        item-embedding.enabled: true
        user-preference.enabled: true
      ranking:
        deepfm.enabled: true
        fallback.enabled: true
      reranking:
        genre-dispersion.enabled: true
        decade-dispersion.enabled: true
      coldstart:
        ucb-genre.enabled: true
        preferred-genre.enabled: true
        popular-recent.enabled: true
```

---

## 五、离线模型需求清单

### 5.1 YouTubeDNN 召回模型

| 项目 | 说明 |
|------|------|
| 端点 | `POST /api/predict/recall` |
| 输入 | `user_features` (userId, gender, age, occupation, zipCode) + `hist_movie_ids` |
| 输出 | `user_vector`: 16维 float 数组 |
| 关键 | 输出维度必须与 `item_emb.npy` 列数一致 |
| 特征编码 | 模型内部完成（LabelEncoder / Embedding 层），在线侧传原始值 |

### 5.2 DeepFM 精排模型

| 项目 | 说明 |
|------|------|
| 端点 | `POST /api/predict/ranking` |
| 输入 | `user_features` + `item_features[]` (每个候选一条) |
| 输出 | `List[{movie_id, ctr_score}]` — 按输入顺序返回 |
| 关键 | 返回的 `movie_id` 对应输入中的 `movie_id`，用于映射回候选集 |
| 特征编码 | 模型内部完成，在线侧传原始值 |
| 注意 | 当前只传 3 个物品特征，真实模型需要更多列，需对齐训练时的特征配置 |

### 5.3 Item Embedding (离线预计算)

| 项目 | 说明 |
|------|------|
| 产出 | `item_emb.npy` — (N, dim) float64 矩阵 |
| 配套 | `movie_ids.npy` — (N,) int64 数组，第 i 行对应 movieIds[i] |
| 维度 | 当前 16 维，可扩展，但需与 YouTubeDNN user_vector 维度一致 |
| 用途 | YouTubeDNN 点积召回 + ItemEmbedding 相似物品召回 |

---

## 六、评分反馈闭环

```
用户评分 (POST /api/ratings)
    │
    ├─→ PG ratings 表 INSERT (已重评时 DELETE + INSERT)
    ├─→ PG movies.avg_rating / rating_count 实时重算 (AVG + COUNT)
    ├─→ Redis user:{id}:history LPUSH (去重未实现，同一 movie 可重复)
    ├─→ Redis user:{id}:genre_ucb HINCR (n+1, reward+rating)
    └─→ 下次推荐时：
         ├─ history → 召回候选 (YouTubeDNN / ItemEmbedding)
         └─ UCB stats → 冷启动类型选择
```

---

## 七、开发指引

### 接真实模型的 Checklist

1. **替换 mock 推理服务**：修改 `inference-service/main.py` 加载实际模型
2. **特征对齐**：确保 Python 侧的 LabelEncoder / feature columns 与 Java 侧传递的字段名匹配
3. **维度对齐**：`user_vector` 长度 == `item_emb.npy` 列数
4. **NPY 更新**：离线训练产出新的 `item_emb.npy` + `movie_ids.npy`，放到 `data/` 目录
5. **超时时长**：`RecommendationPipeline.timeout` 当前 800ms，真实模型可能需要调大

### 冷启动优化方向

- 当前 `ColdStartDetection` 阈值为 `history.size() < 5`，可在 `application.yml` 配置化
- 新用户完全无 UCB 数据时，`UCBGenreStrategy` fallback 到 `PopularRecentStrategy`
- 可增加 `ColdStartStrategy` 实现（如热门 + 新上映 + 编辑精选混合）

### 召回策略扩展

- 实现 `RecallStrategy` 接口 + `@Component` + `@ConditionalOnProperty`，自动注册到 `RecallStrategyRegistry`
- `getName()` 返回值会写入 `RecallItem.recallType`，用于下游区分来源

### 重排策略扩展

- 继承 `RerankingStrategy` 接口
- 可基于 `ConsecutiveDispersionStrategy` 模式扩展新的打散维度（导演、语言等）
- 多个重排策略按 Registry 顺序链式执行
