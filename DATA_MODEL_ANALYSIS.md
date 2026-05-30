# Rec 电影推荐系统 — 数据模型与数据流分析

## 项目概况

这是一个 **Python FastAPI** 后端项目，遵循经典的**推荐系统三层架构**：

```
app/        → Web API 层（FastAPI）
online/     → 在线推荐管线（召回 → 排序 → 重排）
offline/    → 离线训练管线（特征工程 → 训练 → 部署）
```

**基础设施**: PostgreSQL（主存储）+ Redis（缓存/用户特征）+ Elasticsearch（全文搜索/召回查询）+ 本地文件系统（TF 模型存储）

---

## 一、数据模型总览

### 1.1 SQLAlchemy ORM 实体（9 张表）— `app/models.py`

| 实体 | 表名 | 核心字段 | 关系 |
|------|------|---------|------|
| **User** | `users` | user_id, email, username, hashed_password, gender, age, occupation, zip_code, preferred_genres[] | 1:N → Rating |
| **Movie** | `movies` | movie_id, imdb_id, title, year, genres[], description, avg_rating, rating_count, imdb_rating | 1:N → Rating |
| **Rating** | `ratings` | user_id + movie_id (联合PK), rating (1-10), timestamp | N:1 → User, N:1 → Movie |
| **Genre** | `genres` | id, name | 独立字典表 |
| **TitleRating** | `title_ratings` | tconst (PK), average_rating, num_votes | IMDb 评分聚合 |
| **NameBasics** | `name_basics` | nconst (PK), primary_name, birth_year, primary_profession[] | IMDb 人物 |
| **TitleCrew** | `title_crew` | tconst (PK), directors[], writers[] | IMDb 剧组 |
| **TitlePrincipal** | `title_principals` | tconst + ordering (联合PK), nconst, category, characters | IMDb 主演 |
| **TitleAka** | `title_akas` | tconst + ordering (联合PK), title, region, language | IMDb 别名 |

**核心关系**: `User ──1:N── Rating ──N:1── Movie`

#### 各实体完整字段

**User** (`users`)
| 字段 | 类型 | 说明 |
|------|------|------|
| user_id | Integer, PK | 自增主键 |
| email | String(255), unique, nullable | 邮箱 |
| username | String(100), unique, nullable | 用户名 |
| hashed_password | String(255), nullable | bcrypt 哈希密码 |
| is_active | Integer, default=1 | 激活状态 |
| is_superuser | Integer, default=0 | 管理员标识 |
| gender | String(1) | 性别 |
| age | String(20) | 年龄段 |
| occupation | String(100) | 职业 |
| zip_code | String(10) | 邮编 |
| created_at | DateTime | 创建时间 |
| preferred_genres | ARRAY(String) | 偏好类型列表 |

**Movie** (`movies`)
| 字段 | 类型 | 说明 |
|------|------|------|
| movie_id | Integer, PK | 主键 |
| imdb_id | String(20), unique | IMDb ID |
| title | String(255), index | 标题 |
| year | Integer, index | 发行年份 |
| genres | ARRAY(String) | 类型列表 |
| description | Text | 剧情描述 |
| avg_rating | Float, index | 站内平均评分 |
| rating_count | Integer, default=0 | 评分人数 |
| imdb_rating | Float, index | IMDb 评分 |
| imdb_votes | Integer | IMDb 评分人数 |
| title_type | String(50) | 类型 (movie/series...) |
| runtime_minutes | Integer | 片长 |
| is_adult | Integer, default=0 | 成人内容标识 |
| created_by | Integer, FK→users | 创建者 |

**Rating** (`ratings`)
| 字段 | 类型 | 说明 |
|------|------|------|
| user_id | Integer, PK, FK→users | 用户 |
| movie_id | Integer, PK, FK→movies | 电影 |
| rating | Integer | 评分 (1-10) |
| timestamp | BigInteger | 评分时间戳 |

**Genre** (`genres`)
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer, PK, autoincrement | 自增主键 |
| name | String(50), unique | 类型名称 |

**TitleRating** (`title_ratings`)
| 字段 | 类型 | 说明 |
|------|------|------|
| tconst | String(20), PK | IMDb 标题 ID |
| average_rating | Float, index | IMDb 平均评分 |
| num_votes | Integer, index | IMDb 评分人数 |

**NameBasics** (`name_basics`)
| 字段 | 类型 | 说明 |
|------|------|------|
| nconst | String(20), PK | IMDb 人物 ID |
| primary_name | String(255), index | 姓名 |
| birth_year | Integer | 出生年份 |
| death_year | Integer | 逝世年份 |
| primary_profession | ARRAY(String) | 主要职业 |
| known_for_titles | ARRAY(String) | 代表作标题 ID 列表 |

**TitleCrew** (`title_crew`)
| 字段 | 类型 | 说明 |
|------|------|------|
| tconst | String(20), PK | IMDb 标题 ID |
| directors | ARRAY(String) | 导演 nconst 列表 |
| writers | ARRAY(String) | 编剧 nconst 列表 |

**TitlePrincipal** (`title_principals`)
| 字段 | 类型 | 说明 |
|------|------|------|
| tconst | String(20), PK | IMDb 标题 ID |
| ordering | Integer, PK | 排序号 |
| nconst | String(20), index | IMDb 人物 ID |
| category | String(50) | 角色类别 (actor/director...) |
| job | String(255) | 具体职务 |
| characters | Text | 饰演角色 (JSON 格式) |

**TitleAka** (`title_akas`)
| 字段 | 类型 | 说明 |
|------|------|------|
| tconst | String(20), PK | IMDb 标题 ID |
| ordering | Integer, PK | 排序号 |
| title | String(500), index | 本地化标题 |
| region | String(10) | 国家/地区代码 |
| language | String(10) | 语言代码 |
| types | String(100) | 别名类型 |
| attributes | String(255) | 附加属性 |
| is_original_title | Integer | 是否原始标题 |

### 1.2 Pydantic Schema 类（27 个）— `app/schemas.py`

> 所有 Schema 均继承 `pydantic.BaseModel`，配置 `model_config = ConfigDict(from_attributes=True)` 以支持 ORM 模式。

#### 请求体

| 类名 | 字段 | 用途 |
|------|------|------|
| **MovieCreate** | title, imdb_id?, year? (1888-2099), genres?[], description?, runtime_minutes? (>0), title_type?, imdb_rating? (0-10), imdb_votes? (≥0) | 创建电影 |
| **UserSignup** | email, password (min 6), gender?, age?, occupation?, zip_code?, preferred_genres?[] | 用户注册 |
| **UserLogin** | email, password | 用户登录 |
| **UserUpdate** | gender?, age?, occupation?, zip_code?, preferred_genres?[] | 更新用户资料 |
| **RatingCreate** | movie_id, rating (1-10) | 提交评分 |

#### 响应体

| 类名 | 字段 | 用途 |
|------|------|------|
| **MovieBase** | title, year?, genres[], description? | 电影基类 |
| **MovieDetail** | MovieBase + movie_id, imdb_id?, avg_rating?, rating_count?, imdb_rating?, imdb_votes?, runtime_minutes?, title_type? | 电影详情 |
| **MovieListItem** | movie_id, title, year?, genres[], avg_rating?, imdb_rating? | 电影列表项 |
| **MovieList** | items[], total, page, page_size, has_next | 分页列表封装 |
| **UserBase** | email, username, gender?, age?, occupation?, zip_code? | 用户基类 |
| **UserProfile** | user_id, email, username, gender?, age?, occupation?, zip_code?, is_superuser, created_at, preferred_genres[], frequent_genres[] (计算字段), recent_ratings[] | 用户主页 |
| **UserDetail** | UserBase + user_id, created_at | 用户详情 |
| **Token** | access_token, token_type (default "bearer") | 登录响应 |
| **TokenData** | user_id? | JWT payload |
| **RatingBase** | user_id, movie_id, rating (1-5) | 评分基类 |
| **RatingDetail** | RatingBase + timestamp | 评分详情 |
| **RecentRating** | movie_id, title, genres[], rating, timestamp | 最近评分项 |
| **HealthCheck** | status, version, database, redis, elasticsearch | 健康检查 |
| **PersonBase** | person_id, name, birth_year?, death_year? | 人物基类 |
| **PersonDetail** | PersonBase + professions[], known_for_titles[] | 人物详情 |
| **CastMember** | person_id, name, character?, category, ordering | 演员信息 |
| **CrewMember** | 继承 PersonBase (无额外字段) | 剧组信息 |
| **MovieCast** | movie_id, movie_title, cast[] | 电影演员聚合 |
| **MovieCrew** | movie_id, movie_title, directors[], writers[] | 电影剧组聚合 |
| **GenreResponse** | id, name | 类型响应 |
| **GenreListResponse** | genres[] | 类型列表封装 |

### 1.3 端点内联 Schema — `endpoints/*.py`

**`recommendations.py`**

| 类名 | 字段 | 用途 |
|------|------|------|
| **UserFeaturesRequest** | user_id?, gender?, age?, occupation?, zip_code?, hist_movie_ids[], preferred_genres[] | 推荐请求 |
| **RecommendationItemResponse** | movie_id, title, genres[], score, recall_score?, recall_type?, poster_url? | 单条推荐结果 |
| **RecommendationResponse** | items[], recall_count, ranking_strategy | 推荐响应 |

**`ratings.py`**

| 类名 | 字段 | 用途 |
|------|------|------|
| **RatingResponse** | user_id, movie_id, rating, timestamp | 评分响应 |
| **UserRatingResponse** | rating \| null, has_rated | 用户对某电影的评分状态 |

### 1.4 管线内部 Dataclass — `online/pipeline.py`

| 类名 | 字段 | 用途 |
|------|------|------|
| **PipelineConfig** | recall_top_k=100, ranking_top_k=20, enable_ranking=True, enable_reranking=True, enable_cold_start=True, cold_start_threshold=5, cold_start_top_k=20 | 管线参数 |
| **RecommendationItem** | movie_id (int), score (float), recall_score? (float), recall_type? (str) | 管线内候选 item |
| **RecommendationResult** | items (List[RecommendationItem]), recall_count (int), ranking_strategy (str), reranking_strategies (List[str]), is_cold_start (bool) | 管线输出 |

### 1.5 配置类

**`app/config.py` — Settings** (Pydantic BaseSettings)

| 字段 | 默认值 | 说明 |
|------|--------|------|
| app_name | "Rec" | 应用名 |
| app_version | "1.0.0" | 版本号 |
| debug | False | 调试模式 |
| database_url | postgresql://rec:rec123@localhost:5432/rec_db | PG 连接串 |
| redis_url | redis://localhost:6379/0 | Redis 连接串 |
| redis_ttl | 600 | Redis 缓存 TTL (秒) |
| elasticsearch_url | http://localhost:9200 | ES 连接串 |
| secret_key | (必填) | JWT 签名密钥 |
| algorithm | "HS256" | JWT 算法 |
| access_token_expire_minutes | 30 | Token 过期时间 |
| recall_candidate_size | 100 | 召回候选数 |
| ranking_candidate_size | 20 | 排序后保留数 |
| reranking_result_size | 20 | 重排后保留数 |

**`offline/config.py` — Config**

| 字段 | 默认值 | 说明 |
|------|--------|------|
| MAX_SEQ_LEN | 10 | 最大用户历史序列长度 |
| EMB_DIM | 16 | Embedding 维度 |
| NEG_SAMPLE_SIZE | 20 | 负采样数量 |
| BATCH_SIZE | 128 | 训练 batch size |
| EPOCHS | 3 | 训练轮数 |
| LEARNING_RATE | 0.001 | 学习率 |
| REDIS_URL | redis://localhost:6379/0 | Redis 连接串 |
| USER_PROFILE_PREFIX | "user" | Redis 用户画像 key 前缀 |
| USER_HISTORY_PREFIX | "user" | Redis 用户历史 key 前缀 |

### 1.6 策略抽象接口（4 个 ABC）

| 接口 | 核心方法 | 所在模块 |
|------|---------|---------|
| **RecallStrategy** | `recall(user_context: Dict, k: int) → List[Dict]` | `online/recall/base.py` |
| **RankingStrategy** | `rank(user_features: Dict, candidates: List[Dict]) → List[Dict]` | `online/ranking/base.py` |
| **RerankingStrategy** | `rerank(items: List[Dict], user_features: Dict) → List[Dict]` | `online/reranking/base.py` |
| **ColdStartStrategy** | `recommend(user_features: Dict, k: int) → List[Dict]` + `can_handle(user_features: Dict) → bool` | `online/cold_start/base.py` |

### 1.7 策略实现——完整列表

| 接口 | 实现类 | 文件 | 状态 |
|------|--------|------|------|
| RecallStrategy | **UserPreferenceRecallStrategy** | `recall/trending.py` | 激活 |
| RecallStrategy | GlobalTrendingRecallStrategy | `recall/trending.py` | 禁用 |
| RecallStrategy | YouTubeDNNRecallStrategy | `recall/youtubednn.py` | 禁用 |
| RecallStrategy | ItemEmbeddingRecallStrategy | `recall/item_based.py` | 禁用 |
| RankingStrategy | **DeepFMRankingStrategy** | `ranking/deepfm.py` | 激活 |
| RankingStrategy | **FallbackRankingStrategy** | `ranking/deepfm.py` | 降级 |
| RerankingStrategy | **GenreDispersionStrategy** | `reranking/dispersion.py` | 激活 |
| RerankingStrategy | **DecadeDispersionStrategy** | `reranking/dispersion.py` | 激活 |
| ColdStartStrategy | **UCBGenreStrategy** (70%) | `cold_start/ucb_genre.py` | 激活 |
| ColdStartStrategy | **PreferredGenreStrategy** (10%) | `cold_start/preferred_genre.py` | 激活 |
| ColdStartStrategy | **PopularRecentStrategy** (20%) | `cold_start/popular.py` | 激活 |

### 1.8 服务单例——完整列表

| 类名 | 文件 | 获取方式 |
|------|------|---------|
| **RecommendationPipeline** | `online/pipeline.py` | `get_pipeline()` |
| **RecallService** | `online/recall/service.py` | `get_recall_service()` |
| **RankingService** | `online/ranking/service.py` | `get_ranking_service()` |
| **RerankingService** | `online/reranking/service.py` | `get_reranking_service()` |
| **ColdStartService** | `online/cold_start/service.py` | `get_cold_start_service()` |
| **ColdStartDetector** | `online/cold_start/detector.py` | 阈值判断 (5 条交互) |
| **RecallResourceManager** | `online/recall/resource_manager.py` | 单例, 加载召回模型/词典/embedding |
| **RankingResourceManager** | `online/ranking/resource_manager.py` | 单例, 加载 DeepFM 模型/词典 |
| **ElasticsearchService** | `app/services/elasticsearch_service.py` | 模块级 `es_service` |

---

## 二、Online 数据流程（实时推荐）

### 入口: `POST /api/recommendations/recommend`

```
HTTP Request
{user_id, gender, age, occupation, zip_code, hist_movie_ids[], preferred_genres[]}
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│  端点层: recommendations.py                                      │
│  1. Pydantic 校验 → UserFeaturesRequest                         │
│  2. enrich_user_features(): 从 DB 补充用户画像                    │
│  3. 构建 item_features_provider 闭包 (惰性查 DB)                  │
│  4. 调用 pipeline.recommend(user_features, provider, config)     │
└─────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│  管线编排: online/pipeline.py → RecommendationPipeline           │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 阶段 1: 冷启动检测 (ColdStartDetector)                      │  │
│  │                                                           │  │
│  │   hist_movie_ids < 5 ?                                     │  │
│  │                                                           │  │
│  │   YES → 冷启动路径:                                         │  │
│  │     UCBGenreStrategy → ES 查询 UCB 最优 genre 的电影        │  │
│  │     PreferredGenreStrategy → ES 查询偏好 genre 的电影        │  │
│  │     PopularRecentStrategy → ES 查询热门高分电影              │  │
│  │     结果 round-robin 合并 → 跳至响应                         │  │
│  │                                                           │  │
│  │   NO → 正常管线继续 ↓                                       │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 阶段 2: 多路召回 (RecallService)                            │  │
│  │                                                           │  │
│  │   读 Redis:                                                │  │
│  │     user:{id}:profile → Hash (用户画像)                     │  │
│  │     user:{id}:history → List (历史观影序列)                  │  │
│  │                                                           │  │
│  │   当前激活策略:                                              │  │
│  │     UserPreferenceRecallStrategy → ES 按用户高频 genre 检索  │  │
│  │     (YouTubeDNN / ItemEmbedding / GlobalTrending 已注释)    │  │
│  │                                                           │  │
│  │   多路结果 round-robin 蛇形合并 → ~100 候选                   │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 阶段 3: CTR 排序 (RankingService)                           │  │
│  │                                                           │  │
│  │   从 DB 获取候选物品特征 (item_features_provider)            │  │
│  │                                                           │  │
│  │   策略: DeepFMRankingStrategy                               │  │
│  │     将 user + item 特征经 LabelEncoder 编码                 │  │
│  │     调用 TF DeepFM 模型 predict(CTR) 在线程池中推理          │  │
│  │     按预测 CTR 降序排列                                      │  │
│  │                                                           │  │
│  │   降级: FallbackRankingStrategy → 按召回分数排序              │  │
│  │                                                           │  │
│  │   输出 → top 20 items                                       │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 阶段 4: 多样性重排 (RerankingService)                        │  │
│  │                                                           │  │
│  │   GenreDispersionStrategy: 连续不超过 2 部同 genre          │  │
│  │   DecadeDispersionStrategy: 连续不超过 2 部同年代            │  │
│  │                                                           │  │
│  │   贪心算法: 顺序处理, 违反约束的延迟到后面                     │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  输出: RecommendationResult                                    │
└─────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│  响应组装: enrich_with_metadata()                                │
│    从 DB 查电影 title、genres、poster_url                         │
│    → RecommendationResponse (JSON)                              │
└─────────────────────────────────────────────────────────────────┘
```

### 反馈闭环（评分 → 更新 Redis UCB 统计）

```
POST /api/ratings (用户打分)
  ├── 更新 PostgreSQL: Rating 表 + Movie.avg_rating
  ├── 更新 Elasticsearch: 同步评分到 ES 索引
  ├── 更新 Redis user:{id}:history: LPUSH movie_id
  ├── 更新 Redis user:{id}:profile: 重新计算 frequent_genres
  └── 更新 Redis user:{id}:genre_ucb: update_ucb_genre_stats()
         └── 影响后续 UCBGenreStrategy 的探索/利用决策
```

### Redis Key 结构汇总

| Key Pattern | 类型 | 内容 | 写入方 | 读取方 |
|-------------|------|------|--------|--------|
| `user:{id}:profile` | Hash | gender, age, occupation, zip_code, frequent_genres | `offline/storage/redis_ingest.py` + ratings 端点 | `RecallService` |
| `user:{id}:history` | List | 按时间排列的 movie_id 序列 | `offline/storage/redis_ingest.py` + ratings 端点 | `RecallService` |
| `user:{id}:genre_ucb` | Hash | 每种 genre 的 `{n, reward}` JSON | ratings 端点 (`update_ucb_genre_stats()`) | `UCBGenreStrategy` |

---

## 三、Offline 数据流程（批量训练）

Offline 管线**无自动调度**（无 Celery/Airflow/Cron），全部通过 CLI 手动触发：

```bash
make run-offline-pipeline              # 全流程: --steps all --flush-redis
make ingest-data-to-database           # 单步: 数据入库
make index-movies-to-elasticsearch     # 单步: ES 索引构建
make ingest-to-redis                   # 单步: Redis 用户数据灌入
```

### 全流程 6 步

```
┌─────────────────────────────────────────────────────────────────────┐
│ Step 1: 数据入库                                                     │
│   scripts/ingest_data_to_database.py                                │
│                                                                     │
│   输入: 原始 MovieLens + IMDb pickle 文件                             │
│   输出: PostgreSQL 全部 9 张表                                       │
│   调用方式: python scripts/ingest_data_to_database.py                │
│            [--reset] [--create-test-user]                           │
│                                                                     │
│   写入表: users, movies, ratings, genres, title_ratings,             │
│           name_basics, title_crew, title_principals, title_akas      │
└─────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Step 2: ES 索引构建                                                   │
│   scripts/index_movies_elasticsearch.py                             │
│                                                                     │
│   输入: PostgreSQL movies 表                                         │
│   输出: Elasticsearch "movies" 索引                                  │
│                                                                     │
│   索引 Mapping:                                                      │
│     title     → text + completion (suggest)                         │
│     genres    → keyword                                             │
│     year      → integer                                             │
│     avg_rating, imdb_rating, rating_count, imdb_votes → float/int   │
│     description → text                                              │
└─────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Step 3: 召回特征工程                                                  │
│   offline/feature/preprocess_retrieval.py                           │
│                                                                     │
│   输入: 原始 ratings, movies, users pickle                           │
│   处理:                                                              │
│     - 构建 LabelEncoder 词典 (user_id, gender, age, movie_id, ...)   │
│     - 滑动窗口生成序列样本:                                            │
│        对每用户, 最后 1 条进测试集, 其余用滑动窗口进训练集               │
│     - Padding/truncate 到 MAX_SEQ_LEN=10                            │
│   输出:                                                              │
│     - train_eval_sample_final.pkl (训练/评估样本)                     │
│     - vocab_dict.pkl (特征词典)                                      │
│     - feature_dict.pkl (特征配置)                                    │
└─────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Step 4: 排序特征工程                                                  │
│   offline/feature/preprocess_ranking.py                             │
│                                                                     │
│   输入: 原始 ratings, movies, users pickle                           │
│   处理:                                                              │
│     - 取每部电影第一个 genre (DeepFM 要求标量特征)                      │
│     - LabelEncoder 编码全特征 (1-indexed, 0=unknown)                  │
│     - 生成 3 类样本:                                                  │
│        正样本: rating ≥ user_avg - 0.5 (click=True)                  │
│        困难负样本: 有曝光但 rating 低于阈值                             │
│        随机负样本: 用户从未交互过的物品                                 │
│     - 按时序 timestamp 切分 train/test                                │
│   输出:                                                              │
│     - ranking_train_eval_sample.pkl                                  │
│     - ranking_vocab_dict.pkl (编码词典)                               │
│     - ranking_feature_dict.pkl (特征配置)                             │
└─────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Step 5: 模型训练                                                      │
│                                                                     │
│   offline/training/train_retrieval.py                               │
│     模型: YouTubeDNN 双塔                                            │
│       user_tower: user 特征 (id, gender, age...) + 历史序列 → vector │
│       item_tower: target item 特征 → vector                          │
│     损失: sampled_softmax_loss, NEG_SAMPLE_SIZE=20                   │
│     输出: user_model (Keras), item_model, item_embeddings.npy        │
│     评估: Recall@5, Recall@10                                        │
│     配置: EMB_DIM=16, BATCH_SIZE=128, EPOCHS=3, LR=0.001             │
│                                                                     │
│   offline/training/train_ranking.py                                 │
│     模型: DeepFM CTR 预估                                            │
│       DNN hidden layers: [128, 64, 32], dropout=0.1                  │
│       所有特征同时输入 deepfm (FM 交叉) 和 linear (一阶) 组             │
│     损失: binary_crossentropy                                        │
│     评估: AUC, gAUC                                                  │
│     输出: TensorFlow SavedModel                                      │
│     配置: 同召回训练参数                                               │
└─────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Step 6: 部署                                                         │
│                                                                     │
│   offline/storage/redis_ingest.py                                   │
│     读原始数据 pickle → 写 Redis                                     │
│       写入 user:{id}:profile → Hash(gender, age, occupation,         │
│                              zip_code, frequent_genres)              │
│       写入 user:{id}:history → List[movie_id...] (时间序)             │
│       计算 top-3 frequent_genres per user                            │
│     可选 --flush 清空 Redis 后重新灌入                                │
│                                                                     │
│   offline/storage/local_deploy.py                                   │
│     复制 trained models → shared deploy directory                   │
│        deployed_models/model/user_recall/v1/user_model/             │
│        deployed_models/model/ranking/v1/ranking_model/              │
│        + active.json 版本指针                                        │
│        + vocab_dict.pkl, feature_dict.pkl                           │
│        + item_embeddings.npy, movie_ids.npy                         │
└─────────────────────────────────────────────────────────────────────┘
```

### Offline → Online 桥接方式

```
Offline 产出                           Online 消费
─────────────────────────────────────────────────────────────────
Redis user:{id}:profile        →  RecallService._fetch_user_features_from_redis()
Redis user:{id}:history        →  RecallService (用户历史序列, 冷启动检测)
deployed_models/               →  RecallResourceManager (vocab_dict, embeddings, user_model)
  user_recall/v1/              →  RankingResourceManager (vocab_dict, feature_dict, DeepFM model)
deployed_models/
  ranking/v1/
```

### 版本管理

Online 端通过 `active.json` 定位当前活跃的模型版本，位于各模型目录下:

```
deployed_models/model/user_recall/v1/user_model/active.json  → 指向具体版本目录
deployed_models/model/ranking/v1/ranking_model/active.json   → 指向具体版本目录
```

---

## 四、数据访问层总览

本项目**无 Repository 接口、无 DAO 抽象、无 Mapper XML**。数据访问采用直接调用模式。

### 4.1 PostgreSQL — SQLAlchemy 直查

```python
# 典型查询模式 (端点中直接使用)
db.query(User).filter(User.user_id == user_id).first()
db.query(Movie).order_by(Movie.avg_rating.desc()).offset(offset).limit(limit).all()
```

**所有使用 SQLAlchemy 的文件:**

| 文件 | 查询的实体 |
|------|-----------|
| `endpoints/auth.py` | User |
| `endpoints/movies.py` | Movie |
| `endpoints/users.py` | User, Rating |
| `endpoints/ratings.py` | Rating, Movie, User |
| `endpoints/recommendations.py` | Movie, User, Rating |
| `endpoints/genres.py` | Genre |
| `endpoints/people.py` | NameBasics, TitlePrincipal |
| `endpoints/stats.py` | 各表 (聚合查询) |
| `endpoints/health.py` | 原始 SQL 连接检查 |
| `online/cold_start/ucb_genre.py` | Genre (惰性加载) |
| `scripts/ingest_data_to_database.py` | 全部 9 张表 (批量导入) |

### 4.2 Redis — 直连操作

| 文件 | 操作类型 | 用途 |
|------|---------|------|
| `offline/storage/redis_ingest.py` | Pipeline 批量写 | 灌入用户画像、历史记录 |
| `online/recall/service.py` | HGETALL / LRANGE | 读取用户画像和历史 |
| `online/cold_start/ucb_genre.py` | HGET / HSET | 读写 UCB 探索统计 |

### 4.3 Elasticsearch — 单例服务

```python
from app.services.elasticsearch_service import es_service
```

| 文件 | 用途 |
|------|------|
| `endpoints/search.py` | 全文搜索 + 自动补全 |
| `online/recall/trending.py` | `UserPreferenceRecallStrategy` / `GlobalTrendingRecallStrategy` 召回查询 |
| `online/cold_start/ucb_genre.py` | UCB genre 下查询高分电影 |
| `online/cold_start/popular.py` | 热门电影查询 |
| `online/cold_start/preferred_genre.py` | 偏好 genre 电影查询 |
| `scripts/index_movies_elasticsearch.py` | 批量索引 |

### 4.4 本地文件 — ResourceManager 单例

| 文件 | 加载内容 | 用途 |
|------|---------|------|
| `RecallResourceManager` | vocab_dict.pkl, item_embeddings.npy, user_model (TF) | 召回阶段特征编码 + 向量检索 |
| `RankingResourceManager` | vocab_dict.pkl, feature_dict.pkl, ranking_model (TF) | 排序阶段特征编码 + CTR 推理 |

---

## 五、完整 API 端点列表

### 认证 `/api/auth`
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/signup` | 用户注册 |
| POST | `/api/auth/login` | 用户登录 |

### 用户 `/api/users`
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/users/me` | 获取当前用户主页 |
| PUT | `/api/users/me` | 更新用户资料 |

### 电影 `/api/movies`
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/movies` | 创建电影 (管理员) |
| GET | `/api/movies` | 电影列表 (分页) |
| GET | `/api/movies/popular` | 热门电影 |
| GET | `/api/movies/{id}` | 电影详情 |
| GET | `/api/movies/{id}/cast` | 电影演员 |
| GET | `/api/movies/{id}/crew` | 电影剧组 |

### 评分 `/api/ratings`
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/ratings` | 提交评分 |
| GET | `/api/ratings/movie/{id}` | 查某电影的评分 |
| DELETE | `/api/ratings/movie/{id}` | 删除评分 |

### 推荐 `/api/recommendations`
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/recommendations/recommend` | 获取个性化推荐 |
| GET | `/api/recommendations/health` | 推荐服务健康检查 |

### 搜索 `/api/search`
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/search/movies` | 电影全文搜索 |
| GET | `/api/search/suggest` | 搜索自动补全 |

### 其他
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/genres` | 类型列表 |
| GET | `/api/people/{id}` | 人物详情 |
| GET | `/api/stats` | 仪表盘统计 |
| GET | `/health` | 全局健康检查 |

---

## 六、数据流总图

```
                     ┌──────────────┐
                     │  原始数据     │
                     │ (MovieLens+  │
                     │  IMDb .pkl)  │
                     └──────┬───────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
        ┌──────────┐ ┌──────────┐ ┌───────────┐
        │PostgreSQL│ │  Redis   │ │    ES     │
        │ (主存储)  │ │ (缓存)   │ │  (搜索)   │
        └─────┬────┘ └────┬─────┘ └─────┬─────┘
              │           │             │
    ┌─────────┼───────────┼─────────────┼─────────┐
    │         │    ONLINE PIPELINE      │         │
    │         │                         │         │
    │  冷启动 ◄──── Redis UCB ──────────┘         │
    │    │                                        │
    │    ├──► UCBGenre ───────────────► ES query  │
    │    ├──► PreferredGenre ─────────► ES query  │
    │    └──► PopularRecent ──────────► ES query  │
    │                                             │
    │  正常管线                                    │
    │    │                                        │
    │    ├──► Recall ◄── Redis(profile+history)   │
    │    │      └──► UserPreference ──► ES query  │
    │    │                                        │
    │    ├──► Ranking ◄── 本地 TF DeepFM 模型     │
    │    │      └──► CTR 预测 → 排序              │
    │    │                                        │
    │    └──► Reranking                           │
    │           └──► Genre/Decade 多样性打散       │
    │                                             │
    │  响应 ◄── DB (movie title/genres/poster)    │
    └─────────────────────────────────────────────┘

         ┌──────────────────────┐
         │   OFFLINE PIPELINE   │
         │                      │
         │  数据入库 ──► PG+ES  │
         │  特征工程 ──► .pkl   │
         │  模型训练 ──► TF     │
         │  Redis 灌入          │
         │  模型部署 ──► 本地   │
         └──────────────────────┘
```

---

## 七、数量统计

| 类别 | 数量 |
|------|------|
| SQLAlchemy ORM 实体 | 9 |
| Pydantic Schema (schemas.py) | 26 |
| Pydantic Schema (端点内联) | 5 |
| Dataclass (管线内部) | 3 |
| 配置类 | 2 |
| 策略抽象接口 (ABC) | 4 |
| 策略实现类 | 11 |
| 服务单例 | 9 |
| 资源管理器 | 2 |
| API 端点 | 20 |

---

## 八、当前已知的注意事项

1. **召回层**: 4 个策略中仅 `UserPreferenceRecallStrategy`（ES 按 genre 召回）处于激活状态；YouTubeDNN、ItemEmbedding、GlobalTrending 在 `online/recall/service.py` 中被注释禁用
2. **排序层**: DeepFM 可用时正常推理，不可用时自动降级为 `FallbackRankingStrategy`（按召回分数排序）
3. **Offline 管线**: 完全手动触发（`make run-offline-pipeline`），无自动定时任务
4. **无 DAO 层**: 数据访问在端点函数中直接使用 `db.query()`，未封装 Repository/DAO 抽象
5. **无 MongoDB**: 项目未使用 MongoDB，存储仅依赖 PostgreSQL + Redis + ES + 本地文件

---

## 九、召回层 (Recall) 详细输入输出

### 9.1 入口函数

`RecallService.recommend(user_features, top_k)` — `online/recall/service.py:150`

### 9.2 输入: `user_features`

| 字段 | 类型 | 必填 | 来源 | 说明 |
|------|------|------|------|------|
| `user_id` | `int` | 否 | 请求体 | 用户标识，用于从 Redis 补充特征 |
| `gender` | `str` | 否 | 请求体 / DB | 性别，如 `"M"`, `"F"` |
| `age` | `int` | 否 | 请求体 / DB | 年龄 |
| `occupation` | `str` | 否 | 请求体 / DB | 职业 |
| `zip_code` | `str` | 否 | 请求体 / DB | 邮编 |
| `hist_movie_ids` | `List[int]` | 否 | 请求体 / DB / Redis | 用户历史观影序列（时间降序） |
| `preferred_genres` | `List[str]` | 否 | 请求体 / DB | 用户显式选择的偏好类型 |
| `frequent_genres` | `List[str]` | 否 | **Redis** `user:{id}:profile` | 从历史行为统计的高频类型（top-3） |

**补充逻辑** (`_fetch_user_features_from_redis`, 行 57-86):
1. 从 Redis `user:{id}:profile` (Hash) 读取画像字段并合并到 `user_features`（不覆盖已有值）
2. 从 Redis `user:{id}:history` (List) 读取历史 movie_id 序列 → `hist_movie_ids`
3. `frequent_genres` 如果是逗号分隔字符串则拆分为 `List[str]`

**执行方式**: 各召回策略并行执行（`asyncio.gather`），各策略独立消费 `user_features`。

### 9.3 当前激活策略的输入消费

| 策略 | 消费的字段 | 查询方式 |
|------|-----------|---------|
| **UserPreferenceRecallStrategy** | `frequent_genres` | ES `terms` 查询 `genres.keyword`，过滤 `avg_rating >= 5`，按 `year desc + avg_rating desc` 排序 |

### 9.4 单条召回结果的内部表示

各策略返回的 `Dict` 结构：

| 字段 | 类型 | 说明 |
|------|------|------|
| `movie_id` | `int` | 电影 ID |
| `score` | `float` | 召回分数。当前为**固定占位值**：`UserPreferenceStrategy` = `0.8`，`GlobalTrendingStrategy` = `1.0`（YouTubeDNN/ItemEmbedding 被注释，它们本应返回模型相似度分数） |
| `recall_type` | `str` | 召回通道标识：`"user_preference"` / `"global_trending"` / `"item_embedding"` / `"youtubednn"` |
| `title` | `str` | 电影标题（ES 返回的冗余字段，后续响应组装时会被覆盖） |
| `genres` | `List[str]` | 电影类型列表（ES 返回的冗余字段，后续会被覆盖） |

### 9.5 多路合并

`_merge_results_round_robin(results_list, top_k)` (行 88-148):
- 对各策略返回的列表做**蛇形轮询合并**（正向→反向→正向...），确保多样性
- 按 `movie_id` 去重（先到先得）
- 输出数量 ≤ `top_k`（默认 100）

### 9.6 输出: `List[Dict[str, Any]]`

输出结构同单条召回结果（见上表），约 100 条。此输出直接传递给排序层作为 `candidates`。

---

## 十、排序层 (Ranking) 详细输入输出

### 10.1 入口函数

`RankingService.rank_with_item_features(user_features, candidates, item_features_map, top_k)` — `online/ranking/service.py:112`

实际由 `pipeline._rank()` 调用（`online/pipeline.py:357`），流程为：
1. 调 `item_features_provider(movie_ids)` 从 DB 获取物品特征
2. 调 `ranking_service.rank_with_item_features()` 执行排序

### 10.2 输入 1: `user_features`

同召回层输入（整个字典透传），排序层关注以下字段用于模型编码：

| 字段 | 对应 DeepFM 特征 | 说明 |
|------|-----------------|------|
| `user_id` | `user_id` | LabelEncoder 编码后作为稀疏特征 |
| `gender` | `gender` | LabelEncoder 编码 |
| `age` | `age` | LabelEncoder 编码 |
| `occupation` | `occupation` | LabelEncoder 编码 |
| `zip_code` | `zip_code` | LabelEncoder 编码 |

### 10.3 输入 2: `candidates`

召回层输出，每项至少包含 `movie_id`。当前召回策略还附带 `score`、`recall_type`、`title`、`genres`。

### 10.4 输入 3: `item_features_map`

由 `get_item_features()` 闭包（`recommendations.py:95-109`）从 PostgreSQL 查询得到，`Dict[int, Dict]` 按 movie_id 索引：

| 字段 | 类型 | 来源 | 说明 |
|------|------|------|------|
| `genres` | `str \| None` | DB `m.genres[0]` | **仅取第一个类型**（DeepFM 要求标量特征，不能是列表） |
| `genres_list` | `List[str]` | DB `m.genres` | 完整类型列表（供重排层用，排序层不使用） |
| `isAdult` | `int` | DB `m.is_adult` | 是否成人内容（0/1） |
| `year` | `int` | DB `m.year` | 发行年份（供重排层年代打散用，排序层不使用） |

**合并方式** (`rank_with_item_features`, 行 135-143):
```python
enriched = {**candidate, **item_feats}  # item_feats 覆盖同名字段
```
合并后每个 candidate 同时拥有召回字段（`score`, `recall_type`）和物品特征（`genres`, `isAdult`, `year`）。

### 10.5 DeepFM 模型推理

`DeepFMRankingStrategy._rank_sync()` (`deepfm.py:87-182`):

1. **特征编码** (`_prepare_batch_inputs`, 行 38-85):
   - 从 `RankingResourceManager` 获取 `user_features` 列表（如 `["user_id", "gender", "age", "occupation", "zip_code"]`）和 `item_features` 列表（如 `["movie_id", "genres", "isAdult"]`）
   - 对每个特征调 `rm.encode_feature(feat, raw_val)` 做 LabelEncoder 转换（字符串→整数索引，0=unknown）
   - 用户特征复制 batch_size 份，物品特征逐 candidate 编码
   - 输出 `Dict[str, np.ndarray]`，每个 value 形状为 `(batch_size,)`，dtype=int32

2. **模型预测** (`resource_manager.ranking_model.predict()`, 行 110-113):
   - TensorFlow SavedModel 批量推理
   - 输出 CTR 预估值（float, 0~1），形状 `(batch_size, 1)` → flatten 为 `(batch_size,)`

3. **结果组装** (行 121-129):
   ```python
   {"movie_id": int, "score": float(CTR), "recall_score": float, "recall_type": str}
   ```

4. **排序**: 按 `score`（CTR 预估值）降序排列

### 10.6 降级策略

`FallbackRankingStrategy.rank()` (`deepfm.py:185-216`):
- 触发条件: DeepFM 模型文件不存在或加载失败
- 逻辑: 仅按 `candidate["score"]`（即召回分数）降序排列
- 输出字段同上，但 `score` = `recall_score`（当前实际都是占位值 0.8）

### 10.7 输出: `List[Dict[str, Any]]`

经 `pipeline._rank()` 调用后，输出被 `top_k`（默认 20）截断。每条 item:

| 字段 | 类型 | 说明 |
|------|------|------|
| `movie_id` | `int` | 电影 ID |
| `score` | `float` | **最终排序分数**。DeepFM 可用时为 CTR 预估值 (0~1)；降级时为召回占位分数 |
| `recall_score` | `float` | 原始召回分数（透传） |
| `recall_type` | `str` | 原始召回来源标识（透传） |

> 注意: 排序层输出**不包含** `title`、`genres` 等元数据字段。最终 HTTP 响应组装时由 `enrich_with_metadata()` 重新从 DB 查询并拼装 `RecommendationItemResponse`。

---

## 十一、召回层 → 排序层 数据流串联

```
RecallService.recommend()
  In:  user_features {
         user_id, gender, age, occupation, zip_code,
         hist_movie_ids, preferred_genres, frequent_genres
       }
       top_k = 100
       
  ┌─ UserPreferenceRecallStrategy (ES 按 genre 检索)
  │    输入: frequent_genres
  │    输出: [{movie_id, score=0.8, recall_type="user_preference", title, genres}, ...]
  └

  多路 round-robin 蛇形合并 → 去重 → 截断 top 100
  
  Out: candidates: List[Dict]  (约 100 条)
         ↓
         ↓  pipeline._rank() 桥接
         ↓  
         1. item_features_provider(candidate_ids)  →  DB 查询
             返回: {movie_id: {genres, genres_list, isAdult, year}}
         
         2. 合并: {**candidate, **item_features}
         
         3. RankingService.rank_with_item_features()
              ↓
            DeepFMRankingStrategy._rank_sync()
              ├─ LabelEncoder 编码 user + item 特征
              ├─ TF DeepFM.predict() → CTR (0~1)
              ├─ 按 CTR 降序排列
              └─ 截断 top 20
              
  Out: ranked_items: List[Dict]  (top 20 条)
         [{movie_id, score(CTR), recall_score, recall_type}, ...]
         
         ↓  进入 RerankingService.rerank()
         ↓  (GenreDispersion + DecadeDispersion 打散)
         ↓  
  Out: reranked_items: List[Dict]  (仍为 20 条, 顺序调整)
         ↓
         ↓  enrich_with_metadata() → DB 查 title/genres/poster
         ↓
  Out: RecommendationResponse → HTTP JSON
```

### 关键注意点

1. **召回分数的实际意义有限**: 当前激活的策略只有 `UserPreferenceRecallStrategy`（ES 查询），返回的 `score` 是固定占位值 0.8，**不是模型计算的相似度**。YouTubeDNN/ItemEmbedding 策略被注释后，多路召回的真正价值（不同语义通道互补）未能体现
2. **排序层完全重写 score**: 无论如何，DeepFM 推理后会**覆盖** `score` 字段为 CTR 预估值；降级时则直接用召回分数作为最终分数
3. **特征编码的容错**: LabelEncoder 对未见过的值返回 0（`encode_feature` 的 unknown 处理），防止线上新值导致崩溃
4. **两次 DB 查询**: `item_features_provider` 在排序阶段查一次 DB（取 genres, isAdult, year），`enrich_with_metadata` 在响应组装时再查一次 DB（取 title, genres, poster_url）——两次查询的字段有重叠但目的不同
