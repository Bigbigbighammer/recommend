# FunRec Java/Spring Boot 重构设计文档

## 概述

将 FunRec 电影推荐系统从 Python FastAPI 重构为 Java 17 + Spring Boot 3.x，全量迁移 20 个 API 端点 + 在线推荐管线。离线模型训练保留 Python，Java 在线层通过 HTTP/gRPC 与 Python 推理服务通信。

### 当前系统 (Python)

- **Web 框架**: FastAPI
- **ORM**: SQLAlchemy (直查, 无 DAO 层)
- **管线**: 同步串行, asyncio.gather 并行召回
- **模型推理**: 本地加载 TF SavedModel
- **策略管理**: 代码注释控制启用/禁用

### 目标系统 (Java)

- **Web 框架**: Spring Boot 3.x + WebFlux (Reactor)
- **ORM**: MyBatis-Plus 3.5+
- **管线**: 全链路响应式 (Mono/Flux), Flux.flatMap 并行召回
- **模型推理**: RPC 客户端 → Python 推理服务
- **策略管理**: Spring Bean + `@ConditionalOnProperty` + yml 配置

---

## 一、模块结构

```
recommend-service/                    # Maven 父 POM
│
├── recommend-api/                    # REST 端点层 (WebFlux)
├── recommend-pipeline/               # 在线推荐管线编排
├── recommend-strategy/               # 策略接口 + 实现
├── recommend-rpc/                    # 模型 RPC 客户端抽象
├── recommend-repository/             # 数据访问层 (MyBatis-Plus + Redis + ES)
└── recommend-common/                 # 公共 DTO/VO/异常/工具
```

### 各模块职责

| 模块 | 职责 | 对外暴露 |
|------|------|---------|
| **recommend-api** | REST 端点 (RouterFunction + Handler), 全局异常映射 | HTTP 接口 |
| **recommend-pipeline** | 推荐管线编排, PipelineContext, 4 个 Stage | 被 API 层调用 |
| **recommend-strategy** | 策略接口 + 11 个实现 + Registry 收集器 | 被 Pipeline 层调用 |
| **recommend-rpc** | ModelInferenceClient 接口 + HTTP/gRPC 实现 | 被 Strategy 层调用 |
| **recommend-repository** | MyBatis-Plus Mapper, Redis/ES Repository, Entity | 被各级调用 |
| **recommend-common** | DTO, VO, 异常类, 工具类 | 所有模块共享 |

### 模块依赖关系

```
recommend-api ──→ recommend-pipeline ──→ recommend-strategy ──→ recommend-rpc
      │                  │                      │
      └──────────────────┼──────────────────────┼──→ recommend-repository
                         │                      │
                         └──────────────────────┘
                                    │
                            recommend-common (所有模块依赖)
```

---

## 二、技术栈

| 层次 | 技术 | 说明 |
|------|------|------|
| 语言 | Java 17 | LTS, Record, 增强 switch |
| 构建 | Maven 3.9+ | 多模块 POM |
| Web 框架 | Spring Boot 3.x + WebFlux | 全链路响应式 |
| 响应式 | Project Reactor (Mono/Flux) | 管线编排 + 并行调用 |
| ORM | MyBatis-Plus 3.5+ | 9 表 Mapper + 分页 + PG ARRAY 类型处理器 |
| DB 连接池 | HikariCP | Spring Boot 默认 |
| Redis | Spring Data Redis Reactive (Lettuce) | 异步读写 |
| ES | Spring Data Elasticsearch | 异步全文搜索 + 召回查询 |
| HTTP 客户端 | Spring WebClient | 异步 HTTP 调用 Python 推理服务 |
| gRPC (预留) | grpc-java + @GrpcClient | 后续切换 |
| 策略注册 | `@ConditionalOnProperty` | yml 控制启用/禁用 |
| 序列化 | Jackson 2.x | JSON |
| 监控 | Micrometer + /actuator | 指标暴露 |
| 虚拟线程 | `spring.threads.virtual.enabled: true` | 处理 MyBatis-Plus 阻塞 I/O |

---

## 三、在线推荐管线数据流

### 入口

```
POST /api/recommendations/recommend
  Request: {user_id, gender, age, occupation, zip_code, hist_movie_ids[], preferred_genres[]}
```

### PipelineContext (不可变, 逐 Stage 传递)

```java
record PipelineContext(
    Map<String, Object> userFeatures,          // 原始请求 + Redis/DB 补充
    List<Long> histMovieIds,                   // 用户历史序列
    boolean isColdStart,                       // Stage 1 设置
    List<RecallItem> recallCandidates,         // Stage 2 产出 (top 100)
    Map<Long, ItemFeatures> itemFeaturesMap,   // Stage 3 DB 查询
    List<RankedItem> rankedItems,              // Stage 3 产出 (top 20)
    List<RecommendationItem> rerankedItems     // Stage 4 产出 (top 20)
) {}
```

### 管线执行

```
Stage 0: 补充用户特征 (并行)
  ├── Redis user:{id}:profile → Hash
  ├── Redis user:{id}:history → List[movie_id]
  └── DB 兜底 (Redis 缺失时)

Stage 1: 冷启动检测
  └── histMovieIds.size() < 5 → 走 coldStartPipeline (短路径)

coldStartPipeline (并行 3 路 → round-robin merge):
  ├── UCBGenreStrategy (70%): Redis UCB → ES 查询
  ├── PreferredGenreStrategy (10%): 偏好 genre → ES 查询
  └── PopularRecentStrategy (20%): 热门高分 → ES 查询

Stage 2: 多路召回 (并行 3 路 → snake merge 去重, top 100)
  ├── UserPreferenceRecallStrategy: ES 按 frequent_genres 检索
  ├── YouTubeDNNRecallStrategy: RPC 获取 user embedding → 向量相似度
  └── ItemEmbeddingRecallStrategy: RPC 获取 user embedding → item 相似度

Stage 3: CTR 排序
  ├── itemFeaturesProvider: DB 查候选电影 genres[0], isAdult, year
  ├── rpcClient.predictCTR(request) → Mono<List<CTRPrediction>>
  ├── 按 ctr_score 降序 → top 20
  └── Fallback: RPC 失败 → FallbackRanking (按召回分排序)

Stage 4: 多样性重排 (内存计算, 无外部依赖)
  ├── GenreDispersionStrategy: 连续 ≤ 2 部同 genre
  └── DecadeDispersionStrategy: 连续 ≤ 2 部同年代

响应组装
  └── enrichWithMetadata: DB 查 title, genres, poster_url → HTTP JSON
```

### 召回 Snake Merge

```java
// 轮询蛇形合并, 确保多样性
List<RecallItem> snakeMerge(List<List<RecallItem>> resultsList, int topK) {
    // resultsList[0] 正向, resultsList[1] 反向, resultsList[2] 正向, ...
    // 蛇形取出, movie_id 去重 (先到先得), 截断 topK
}
```

---

## 四、RPC 客户端抽象

### 接口

```java
public interface ModelInferenceClient {
    Mono<List<CTRPrediction>> predictCTR(RankingRequest request);
    Mono<UserVectorResponse> generateUserVector(RecallRequest request);
    Mono<Boolean> health();
    Mono<ModelVersion> getVersion(String modelType);
}
```

### DTO

```java
record RankingRequest(
    Map<String, Object> userFeatures,
    List<Map<String, Object>> itemFeatures,
    String modelVersion
) {}

record CTRPrediction(long movieId, float ctrScore) {}

record RecallRequest(
    Map<String, Object> userFeatures,
    List<Long> histMovieIds,
    String modelVersion
) {}

record ModelVersion(String modelType, String version, String deployTime) {}
```

### HTTP 实现 (默认)

```java
@Component
@ConditionalOnProperty(name = "recommend.rpc.client", havingValue = "http", matchIfMissing = true)
public class HttpModelInferenceClient implements ModelInferenceClient {

    private final WebClient webClient;

    public HttpModelInferenceClient(
        @Value("${recommend.rpc.inference.base-url}") String baseUrl
    ) {
        this.webClient = WebClient.builder()
            .baseUrl(baseUrl)
            .defaultHeaders(h -> h.setContentType(MediaType.APPLICATION_JSON))
            .build();
    }

    @Override
    public Mono<List<CTRPrediction>> predictCTR(RankingRequest request) {
        return webClient.post()
            .uri("/api/predict/ranking")
            .bodyValue(request)
            .retrieve()
            .onStatus(s -> s.is5xxServerError(),
                      r -> Mono.error(new InferenceException("Model service error")))
            .bodyToMono(new ParameterizedTypeReference<List<CTRPrediction>>() {})
            .timeout(Duration.ofSeconds(2));
    }
}
```

### yml 配置

```yaml
recommend:
  rpc:
    client: http
    inference:
      base-url: http://python-inference:8080
      connect-timeout: 500ms
      read-timeout: 2000ms
      max-retries: 1
```

### gRPC 预留

1. 定义 `.proto` → 生成 Java Stub
2. 实现 `GrpcModelInferenceClient implements ModelInferenceClient`
3. 改 yml `recommend.rpc.client: grpc`

管线调用方零改动。

---

## 五、策略管理

### 接口

```java
public interface RecallStrategy {
    String getName();
    Mono<List<RecallItem>> recall(Map<String, Object> userFeatures, int topK);
}

public interface RankingStrategy {
    String getName();
    Mono<List<RankedItem>> rank(List<RecallItem> candidates,
                                Map<String, Object> userFeatures,
                                Map<Long, ItemFeatures> itemFeaturesMap);
}

public interface RerankingStrategy {
    String getName();
    Mono<List<RankedItem>> rerank(List<RankedItem> items, Map<String, Object> userFeatures);
}

public interface ColdStartStrategy {
    String getName();
    boolean canHandle(Map<String, Object> userFeatures);
    int getWeight();
    Mono<List<RecallItem>> recommend(Map<String, Object> userFeatures, int topK);
}
```

### 策略实现与条件注册

每个策略实现标注 `@Component` + `@ConditionalOnProperty`:

```java
@Component
@ConditionalOnProperty(name = "recommend.strategy.recall.user-preference.enabled",
                       havingValue = "true", matchIfMissing = true)
public class UserPreferenceRecallStrategy implements RecallStrategy {
    @Override
    public String getName() { return "user_preference"; }
    // ...
}
```

### Registry 收集器

```java
@Component
public class RecallStrategyRegistry {
    private final List<RecallStrategy> strategies;

    public RecallStrategyRegistry(List<RecallStrategy> strategies) {
        this.strategies = strategies;  // Spring 注入所有命中的 Bean
    }

    public List<RecallStrategy> getActiveStrategies() {
        return strategies;
    }
}
```

### yml 配置

```yaml
recommend:
  strategy:
    recall:
      user-preference:
        enabled: true
      youtubednn:
        enabled: true
      item-embedding:
        enabled: true
      global-trending:
        enabled: false
    ranking:
      deepfm:
        enabled: true
      fallback:
        enabled: true
    reranking:
      genre-dispersion:
        enabled: true
      decade-dispersion:
        enabled: true
    coldstart:
      ucb-genre:
        enabled: true
        weight: 70
      preferred-genre:
        enabled: true
        weight: 10
      popular-recent:
        enabled: true
        weight: 20
```

---

## 六、数据库 DDL

```sql
-- 1. 用户表
CREATE TABLE users (
    user_id       SERIAL PRIMARY KEY,
    email         VARCHAR(255) UNIQUE,
    username      VARCHAR(100) UNIQUE,
    hashed_password VARCHAR(255),
    is_active     SMALLINT DEFAULT 1,
    is_superuser  SMALLINT DEFAULT 0,
    gender        CHAR(1),
    age           VARCHAR(20),
    occupation    VARCHAR(100),
    zip_code      VARCHAR(10),
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    preferred_genres TEXT[]     -- PostgreSQL ARRAY
);

-- 2. 电影表
CREATE TABLE movies (
    movie_id        SERIAL PRIMARY KEY,
    imdb_id         VARCHAR(20) UNIQUE,
    title           VARCHAR(255),
    year            INTEGER,
    genres          TEXT[],
    description     TEXT,
    avg_rating      FLOAT,
    rating_count    INTEGER DEFAULT 0,
    imdb_rating     FLOAT,
    imdb_votes      INTEGER,
    title_type      VARCHAR(50),
    runtime_minutes INTEGER,
    is_adult        SMALLINT DEFAULT 0,
    created_by      INTEGER REFERENCES users(user_id)
);

CREATE INDEX idx_movies_title ON movies(title);
CREATE INDEX idx_movies_year ON movies(year);
CREATE INDEX idx_movies_avg_rating ON movies(avg_rating);
CREATE INDEX idx_movies_imdb_rating ON movies(imdb_rating);

-- 3. 评分表
CREATE TABLE ratings (
    user_id   INTEGER REFERENCES users(user_id),
    movie_id  INTEGER REFERENCES movies(movie_id),
    rating    INTEGER CHECK (rating >= 1 AND rating <= 10),
    timestamp BIGINT,
    PRIMARY KEY (user_id, movie_id)
);

-- 4. 类型字典表
CREATE TABLE genres (
    id   SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE
);

-- 5. IMDb 标题评分表
CREATE TABLE title_ratings (
    tconst         VARCHAR(20) PRIMARY KEY,
    average_rating FLOAT,
    num_votes      INTEGER
);

CREATE INDEX idx_title_ratings_avg ON title_ratings(average_rating);
CREATE INDEX idx_title_ratings_votes ON title_ratings(num_votes);

-- 6. IMDb 人物表
CREATE TABLE name_basics (
    nconst             VARCHAR(20) PRIMARY KEY,
    primary_name       VARCHAR(255),
    birth_year         INTEGER,
    death_year         INTEGER,
    primary_profession TEXT[],
    known_for_titles   TEXT[]
);

CREATE INDEX idx_name_basics_name ON name_basics(primary_name);

-- 7. IMDb 剧组表
CREATE TABLE title_crew (
    tconst    VARCHAR(20) PRIMARY KEY,
    directors TEXT[],
    writers   TEXT[]
);

-- 8. IMDb 主演/主创表
CREATE TABLE title_principals (
    tconst     VARCHAR(20),
    ordering   INTEGER,
    nconst     VARCHAR(20),
    category   VARCHAR(50),
    job        VARCHAR(255),
    characters TEXT,
    PRIMARY KEY (tconst, ordering)
);

CREATE INDEX idx_title_principals_nconst ON title_principals(nconst);

-- 9. IMDb 别名表
CREATE TABLE title_akas (
    tconst          VARCHAR(20),
    ordering        INTEGER,
    title           VARCHAR(500),
    region          VARCHAR(10),
    language        VARCHAR(10),
    types           VARCHAR(100),
    attributes      VARCHAR(255),
    is_original_title SMALLINT,
    PRIMARY KEY (tconst, ordering)
);

CREATE INDEX idx_title_akas_title ON title_akas(title);
```

---

## 七、数据访问层

### MyBatis-Plus Mapper

```java
@Mapper
public interface UserMapper extends BaseMapper<UserEntity> {
    @Select("SELECT * FROM users WHERE email = #{email} AND is_active = 1")
    UserEntity findByEmail(@Param("email") String email);
}

@Mapper
public interface MovieMapper extends BaseMapper<MovieEntity> { }

@Mapper
public interface RatingMapper extends BaseMapper<RatingEntity> { }
```

其余: `GenreMapper`, `TitleRatingMapper`, `NameBasicsMapper`, `TitleCrewMapper`, `TitlePrincipalMapper`, `TitleAkaMapper`

### 实体映射 (PG ARRAY 类型)

```java
@Data
@TableName("movies")
public class MovieEntity {
    @TableId(type = IdType.AUTO)
    private Long movieId;
    private String title;
    private Integer year;

    @TableField(typeHandler = ArrayTypeHandler.class)
    private String[] genres;

    private String description;
    private Float avgRating;
    private Integer ratingCount;
    // ...
}
```

### Redis

```java
@Component
public class UserProfileRedisRepository {
    Mono<Map<String, String>> getUserProfile(Long userId);
    Mono<List<Long>> getUserHistory(Long userId, int maxLen);
    Mono<Map<String, UCBStat>> getUCBStats(Long userId);
    Mono<Void> updateUCBStats(Long userId, String genre, int reward);
}
```

### ES

```java
@Component
public class MovieSearchRepository {
    Flux<MovieSearchResult> searchByGenres(List<String> genres, int topK);
    Flux<MovieSearchResult> searchByKeyword(String keyword, int from, int size);
    Flux<MovieSearchResult> suggest(String prefix, int limit);
}
```

---

## 八、异常处理与降级

### 异常体系

```
RuntimeException
├── RecommendationException (推荐管线异常)
│   ├── InferenceException (模型推理失败)
│   └── StrategyExecutionException (策略执行异常)
└── DataAccessException (数据访问异常)
```

### 降级链路

| 阶段 | 依赖 | 降级方案 |
|------|------|---------|
| 召回 | ES | ES 异常 → DB SQL (genre LIKE) |
| 召回 | 全部策略 | 全部失败 → 热门兜底 (avg_rating top 100) |
| 排序 | Python RPC | RPC 超时/异常 → FallbackRanking (按召回分排序) |
| 排序 | Fallback 失败 | 透传召回结果不加精排 |
| 重排 | 无外部依赖 | 异常 → 透传排序结果不打散 |
| 冷启动 | Redis UCB + ES | 异常 → ES 查热门电影 |

### 超时控制

```java
// 管线整体
pipeline.recommend(features)
    .timeout(Duration.ofMillis(800));

// 各阶段独立
recallService.recommend().timeout(Duration.ofMillis(300));
rpcClient.predictCTR().timeout(Duration.ofMillis(200));
```

### 全局错误响应

```json
{
  "code": "RECOMMEND_ERROR",
  "message": "...",
  "traceId": "..."
}
```

---

## 九、性能优化

### 连接池配置

| 资源 | 池化 | 配置 |
|------|------|------|
| PostgreSQL | HikariCP | max 20, min idle 5 |
| Redis | Lettuce | max 16, min idle 4 |
| ES WebClient | Reactor Pool | max 10, pending 20 |
| Python RPC WebClient | Reactor Pool | max 20, pending 100 |

### 缓存策略

| 数据 | 位置 | TTL | Key |
|------|------|-----|-----|
| 电影详情 | Redis | 10min | `movie:{id}:detail` |
| 类型列表 | Redis | 30min | `genres:all` |
| 热门电影 | Redis | 5min | `movies:popular` |
| 用户画像 | Redis (已有) | 10min | `user:{id}:profile` |
| 用户向量 | Caffeine 本地 | 5min | `user:{id}:vector` |

### 冷启动快速路径

histMovieIds < 5 → 直接走 coldStartPipeline，跳过召回+排序，200ms 内返回。

### 虚拟线程

```yaml
spring:
  threads:
    virtual:
      enabled: true
```

MyBatis-Plus 阻塞 I/O 操作自动在虚拟线程执行，不阻塞 EventLoop。

---

## 十、API 端点清单 (20 个)

| 方法 | 路径 | Handler | 说明 |
|------|------|---------|------|
| POST | `/api/auth/signup` | AuthHandler | 用户注册 |
| POST | `/api/auth/login` | AuthHandler | 用户登录 |
| GET | `/api/users/me` | UserHandler | 当前用户主页 |
| PUT | `/api/users/me` | UserHandler | 更新用户资料 |
| POST | `/api/movies` | MovieHandler | 创建电影 (管理员) |
| GET | `/api/movies` | MovieHandler | 电影列表 (分页) |
| GET | `/api/movies/popular` | MovieHandler | 热门电影 |
| GET | `/api/movies/{id}` | MovieHandler | 电影详情 |
| GET | `/api/movies/{id}/cast` | MovieHandler | 电影演员 |
| GET | `/api/movies/{id}/crew` | MovieHandler | 电影剧组 |
| POST | `/api/ratings` | RatingHandler | 提交评分 |
| GET | `/api/ratings/movie/{id}` | RatingHandler | 查电影评分 |
| DELETE | `/api/ratings/movie/{id}` | RatingHandler | 删除评分 |
| POST | `/api/recommendations/recommend` | RecommendationHandler | 个性化推荐 (核心) |
| GET | `/api/recommendations/health` | RecommendationHandler | 推荐服务健康检查 |
| GET | `/api/search/movies` | SearchHandler | 电影全文搜索 |
| GET | `/api/search/suggest` | SearchHandler | 搜索自动补全 |
| GET | `/api/genres` | GenreHandler | 类型列表 |
| GET | `/api/people/{id}` | PeopleHandler | 人物详情 |
| GET | `/api/stats` | StatsHandler | 仪表盘统计 |
| GET | `/health` | HealthHandler | 全局健康检查 |

---

## 十一、项目规模估算

| 模块 | 文件数 (估) | 说明 |
|------|-----------|------|
| recommend-api | ~15 | 10 Handler + 5 DTO |
| recommend-pipeline | ~6 | Pipeline + Context + 4 Stage |
| recommend-strategy | ~16 | 4 接口 + 11 实现 + Registry |
| recommend-rpc | ~6 | 1 接口 + 2 实现 + 3 DTO |
| recommend-repository | ~20 | 9 Mapper + 9 Entity + Redis + ES Repository |
| recommend-common | ~40 | 20 DTO/VO + 10 Exception + 10 Utils |
| **合计** | **~100** | 含配置类 |

---

## 十二、与 Python 推理服务的接口约定

### 排序 (DeepFM CTR)

```
POST http://python-inference:8080/api/predict/ranking
Content-Type: application/json

{
  "user_features": {
    "user_id": 1,
    "gender": "M",
    "age": 25,
    "occupation": "engineer",
    "zip_code": "12345"
  },
  "item_features": [
    {"movie_id": 100, "genres": "Action", "isAdult": 0},
    {"movie_id": 200, "genres": "Comedy", "isAdult": 0}
  ],
  "model_version": ""
}

Response:
[
  {"movie_id": 100, "ctr_score": 0.082},
  {"movie_id": 200, "ctr_score": 0.045}
]
```

### 召回 (YouTubeDNN user vector)

```
POST http://python-inference:8080/api/predict/recall
Content-Type: application/json

{
  "user_features": {...},
  "hist_movie_ids": [10, 20, 30, 40, 50],
  "model_version": ""
}

Response:
{
  "user_vector": [0.12, -0.34, ...],   // EMB_DIM=16
  "version": "v1"
}
```

### 健康检查

```
GET http://python-inference:8080/api/health

Response:
{"status": "healthy", "model_version": "v1"}
```

---

## 十三、不纳入本次设计的内容

- 离线训练管线的 Java 重写 (保留 Python)
- gRPC 的 Proto 定义与实现 (预留接口, 后续补充)
- 模型版本管理与 A/B 测试框架
- 分布式链路追踪 (可后续接入 Micrometer Tracing)
- CI/CD 流水线
