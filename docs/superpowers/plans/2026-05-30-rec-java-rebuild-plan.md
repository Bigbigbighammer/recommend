# Rec Java/Spring Boot 重构实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Rec 电影推荐系统从 Python FastAPI 全量迁移到 Java 17 + Spring Boot 3.x (WebFlux)，包含 20 个 API 端点 + 在线推荐管线 + 策略模式 + RPC 模型调用。

**Architecture:** Maven 多模块单体应用。recommend-common → recommend-repository → recommend-rpc → recommend-strategy → recommend-pipeline → recommend-api，逐级依赖。WebFlux 全链路响应式，策略通过 `@ConditionalOnProperty` + yml 驱动，模型推理通过 `ModelInferenceClient` 接口（HTTP 实现）调用 Python 推理服务。

**Tech Stack:** Java 17, Spring Boot 3.x, WebFlux (Reactor), MyBatis-Plus 3.5, PostgreSQL, Redis (Lettuce), Elasticsearch, WebClient, Maven

---

## 文件结构

```
recommend-service/
├── pom.xml                                    # 父 POM, 声明 6 个子模块
├── recommend-common/
│   ├── pom.xml
│   └── src/main/java/com/rec/common/
│       ├── model/
│       │   ├── request/                       # 6 个请求 DTO (Record)
│       │   │   ├── LoginRequest.java
│       │   │   ├── SignupRequest.java
│       │   │   ├── UserUpdateRequest.java
│       │   │   ├── MovieCreateRequest.java
│       │   │   ├── RatingCreateRequest.java
│       │   │   └── UserFeaturesRequest.java
│       │   ├── response/                      # 14 个响应 DTO (Record)
│       │   │   ├── TokenResponse.java
│       │   │   ├── UserProfileResponse.java
│       │   │   ├── MovieDetailResponse.java
│       │   │   ├── MovieListItem.java
│       │   │   ├── MovieListResponse.java
│       │   │   ├── RatingResponse.java
│       │   │   ├── UserRatingResponse.java
│       │   │   ├── RecommendationItemResponse.java
│       │   │   ├── RecommendationResponse.java
│       │   │   ├── PersonDetailResponse.java
│       │   │   ├── CastMemberResponse.java
│       │   │   ├── MovieCastResponse.java
│       │   │   ├── GenreListResponse.java
│       │   │   └── HealthResponse.java
│       │   └── pipeline/                      # 管线内部模型 (Record)
│       │       ├── RecallItem.java
│       │       ├── RankedItem.java
│       │       ├── RecommendationItem.java
│       │       ├── ItemFeatures.java
│       │       ├── CTRPrediction.java
│       │       ├── UserVectorResponse.java
│       │       ├── RankingRequest.java
│       │       ├── RecallRequest.java
│       │       └── ModelVersion.java
│       ├── exception/
│       │   ├── RecommendationException.java
│       │   ├── InferenceException.java
│       │   ├── StrategyExecutionException.java
│       │   ├── DataAccessException.java
│       │   └── AuthException.java
│       └── config/
│           └── RecommendProperties.java       # @ConfigurationProperties
│
├── recommend-repository/
│   ├── pom.xml
│   └── src/main/java/com/rec/repository/
│       ├── entity/
│       │   ├── UserEntity.java
│       │   ├── MovieEntity.java
│       │   ├── RatingEntity.java
│       │   ├── GenreEntity.java
│       │   ├── TitleRatingEntity.java
│       │   ├── NameBasicsEntity.java
│       │   ├── TitleCrewEntity.java
│       │   ├── TitlePrincipalEntity.java
│       │   └── TitleAkaEntity.java
│       ├── mapper/
│       │   ├── UserMapper.java
│       │   ├── MovieMapper.java
│       │   ├── RatingMapper.java
│       │   ├── GenreMapper.java
│       │   ├── TitleRatingMapper.java
│       │   ├── NameBasicsMapper.java
│       │   ├── TitleCrewMapper.java
│       │   ├── TitlePrincipalMapper.java
│       │   └── TitleAkaMapper.java
│       ├── redis/
│       │   └── UserProfileRedisRepository.java
│       ├── es/
│       │   └── MovieSearchRepository.java
│       └── config/
│           └── ArrayTypeHandler.java
│
├── recommend-rpc/
│   ├── pom.xml
│   └── src/main/java/com/rec/rpc/
│       ├── ModelInferenceClient.java
│       └── HttpModelInferenceClient.java
│
├── recommend-strategy/
│   ├── pom.xml
│   └── src/main/java/com/rec/strategy/
│       ├── recall/
│       │   ├── RecallStrategy.java
│       │   ├── UserPreferenceRecallStrategy.java
│       │   ├── YouTubeDNNRecallStrategy.java
│       │   └── ItemEmbeddingRecallStrategy.java
│       ├── ranking/
│       │   ├── RankingStrategy.java
│       │   ├── DeepFMRankingStrategy.java
│       │   └── FallbackRankingStrategy.java
│       ├── reranking/
│       │   ├── RerankingStrategy.java
│       │   ├── GenreDispersionStrategy.java
│       │   └── DecadeDispersionStrategy.java
│       ├── coldstart/
│       │   ├── ColdStartStrategy.java
│       │   ├── UCBGenreStrategy.java
│       │   ├── PreferredGenreStrategy.java
│       │   └── PopularRecentStrategy.java
│       └── registry/
│           ├── RecallStrategyRegistry.java
│           ├── RankingStrategyRegistry.java
│           ├── RerankingStrategyRegistry.java
│           └── ColdStartStrategyRegistry.java
│
├── recommend-pipeline/
│   ├── pom.xml
│   └── src/main/java/com/rec/pipeline/
│       ├── PipelineContext.java
│       ├── RecommendationPipeline.java
│       ├── UserFeatureEnrichmentStage.java
│       ├── ColdStartDetectionStage.java
│       ├── ColdStartPipeline.java
│       ├── RecallStage.java
│       ├── RankingStage.java
│       ├── RerankingStage.java
│       └── SnakeMergeUtil.java
│
└── recommend-api/
    ├── pom.xml
    └── src/main/java/com/rec/api/
        ├── handler/
        │   ├── AuthHandler.java
        │   ├── UserHandler.java
        │   ├── MovieHandler.java
        │   ├── RatingHandler.java
        │   ├── RecommendationHandler.java
        │   ├── SearchHandler.java
        │   ├── GenreHandler.java
        │   ├── PeopleHandler.java
        │   ├── StatsHandler.java
        │   └── HealthHandler.java
        ├── router/
        │   └── ApiRouter.java
        ├── error/
        │   └── GlobalErrorWebExceptionHandler.java
        └── RecommendApplication.java
```

---

### Task 1: 项目脚手架 — Maven 父 POM + 模块结构

**Files:**
- Create: `pom.xml`
- Create: `recommend-common/pom.xml`
- Create: `recommend-repository/pom.xml`
- Create: `recommend-rpc/pom.xml`
- Create: `recommend-strategy/pom.xml`
- Create: `recommend-pipeline/pom.xml`
- Create: `recommend-api/pom.xml`

- [ ] **Step 1: 创建父 POM**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>3.3.0</version>
        <relativePath/>
    </parent>

    <groupId>com.rec</groupId>
    <artifactId>recommend-service</artifactId>
    <version>1.0.0</version>
    <packaging>pom</packaging>
    <name>Rec Recommend Service</name>

    <properties>
        <java.version>17</java.version>
        <mybatis-plus.version>3.5.7</mybatis-plus.version>
    </properties>

    <modules>
        <module>recommend-common</module>
        <module>recommend-repository</module>
        <module>recommend-rpc</module>
        <module>recommend-strategy</module>
        <module>recommend-pipeline</module>
        <module>recommend-api</module>
    </modules>

    <dependencyManagement>
        <dependencies>
            <dependency>
                <groupId>com.rec</groupId>
                <artifactId>recommend-common</artifactId>
                <version>${project.version}</version>
            </dependency>
            <dependency>
                <groupId>com.rec</groupId>
                <artifactId>recommend-repository</artifactId>
                <version>${project.version}</version>
            </dependency>
            <dependency>
                <groupId>com.rec</groupId>
                <artifactId>recommend-rpc</artifactId>
                <version>${project.version}</version>
            </dependency>
            <dependency>
                <groupId>com.rec</groupId>
                <artifactId>recommend-strategy</artifactId>
                <version>${project.version}</version>
            </dependency>
            <dependency>
                <groupId>com.rec</groupId>
                <artifactId>recommend-pipeline</artifactId>
                <version>${project.version}</version>
            </dependency>
            <dependency>
                <groupId>com.baomidou</groupId>
                <artifactId>mybatis-plus-spring-boot3-starter</artifactId>
                <version>${mybatis-plus.version}</version>
            </dependency>
        </dependencies>
    </dependencyManagement>
</project>
```

- [ ] **Step 2: 创建 recommend-common/pom.xml**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <parent>
        <groupId>com.rec</groupId>
        <artifactId>recommend-service</artifactId>
        <version>1.0.0</version>
    </parent>
    <artifactId>recommend-common</artifactId>

    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-validation</artifactId>
        </dependency>
        <dependency>
            <groupId>com.fasterxml.jackson.core</groupId>
            <artifactId>jackson-databind</artifactId>
        </dependency>
    </dependencies>
</project>
```

- [ ] **Step 3: 创建 recommend-repository/pom.xml**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <parent>
        <groupId>com.rec</groupId>
        <artifactId>recommend-service</artifactId>
        <version>1.0.0</version>
    </parent>
    <artifactId>recommend-repository</artifactId>

    <dependencies>
        <dependency>
            <groupId>com.rec</groupId>
            <artifactId>recommend-common</artifactId>
        </dependency>
        <dependency>
            <groupId>com.baomidou</groupId>
            <artifactId>mybatis-plus-spring-boot3-starter</artifactId>
        </dependency>
        <dependency>
            <groupId>org.postgresql</groupId>
            <artifactId>postgresql</artifactId>
            <scope>runtime</scope>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-data-redis-reactive</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-data-elasticsearch</artifactId>
        </dependency>
    </dependencies>
</project>
```

- [ ] **Step 4: 创建 recommend-rpc/pom.xml**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <parent>
        <groupId>com.rec</groupId>
        <artifactId>recommend-service</artifactId>
        <version>1.0.0</version>
    </parent>
    <artifactId>recommend-rpc</artifactId>

    <dependencies>
        <dependency>
            <groupId>com.rec</groupId>
            <artifactId>recommend-common</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-webflux</artifactId>
        </dependency>
    </dependencies>
</project>
```

- [ ] **Step 5: 创建 recommend-strategy/pom.xml**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <parent>
        <groupId>com.rec</groupId>
        <artifactId>recommend-service</artifactId>
        <version>1.0.0</version>
    </parent>
    <artifactId>recommend-strategy</artifactId>

    <dependencies>
        <dependency>
            <groupId>com.rec</groupId>
            <artifactId>recommend-common</artifactId>
        </dependency>
        <dependency>
            <groupId>com.rec</groupId>
            <artifactId>recommend-repository</artifactId>
        </dependency>
        <dependency>
            <groupId>com.rec</groupId>
            <artifactId>recommend-rpc</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-webflux</artifactId>
        </dependency>
    </dependencies>
</project>
```

- [ ] **Step 6: 创建 recommend-pipeline/pom.xml**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <parent>
        <groupId>com.rec</groupId>
        <artifactId>recommend-service</artifactId>
        <version>1.0.0</version>
    </parent>
    <artifactId>recommend-pipeline</artifactId>

    <dependencies>
        <dependency>
            <groupId>com.rec</groupId>
            <artifactId>recommend-common</artifactId>
        </dependency>
        <dependency>
            <groupId>com.rec</groupId>
            <artifactId>recommend-strategy</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-webflux</artifactId>
        </dependency>
    </dependencies>
</project>
```

- [ ] **Step 7: 创建 recommend-api/pom.xml**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <parent>
        <groupId>com.rec</groupId>
        <artifactId>recommend-service</artifactId>
        <version>1.0.0</version>
    </parent>
    <artifactId>recommend-api</artifactId>

    <dependencies>
        <dependency>
            <groupId>com.rec</groupId>
            <artifactId>recommend-pipeline</artifactId>
        </dependency>
        <dependency>
            <groupId>com.rec</groupId>
            <artifactId>recommend-repository</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-webflux</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-actuator</artifactId>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
            </plugin>
        </plugins>
    </build>
</project>
```

- [ ] **Step 8: 验证构建**

```bash
mvn validate
```

Expected: BUILD SUCCESS

- [ ] **Step 9: 提交**

```bash
git add pom.xml recommend-*/pom.xml
git commit -m "feat: add Maven multi-module project scaffold"
```

---

### Task 2: Common — 请求 DTO (Record)

**Files:**
- Create: `recommend-common/src/main/java/com/rec/common/model/request/LoginRequest.java`
- Create: `recommend-common/src/main/java/com/rec/common/model/request/SignupRequest.java`
- Create: `recommend-common/src/main/java/com/rec/common/model/request/UserUpdateRequest.java`
- Create: `recommend-common/src/main/java/com/rec/common/model/request/MovieCreateRequest.java`
- Create: `recommend-common/src/main/java/com/rec/common/model/request/RatingCreateRequest.java`
- Create: `recommend-common/src/main/java/com/rec/common/model/request/UserFeaturesRequest.java`

- [ ] **Step 1: 创建 LoginRequest**

```java
package com.rec.common.model.request;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;

public record LoginRequest(
    @NotBlank @Email String email,
    @NotBlank String password
) {}
```

- [ ] **Step 2: 创建 SignupRequest**

```java
package com.rec.common.model.request;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import java.util.List;

public record SignupRequest(
    @NotBlank @Email String email,
    @NotBlank @Size(min = 6) String password,
    String gender,
    String age,
    String occupation,
    String zipCode,
    List<String> preferredGenres
) {}
```

- [ ] **Step 3: 创建 UserUpdateRequest**

```java
package com.rec.common.model.request;

import java.util.List;

public record UserUpdateRequest(
    String gender,
    String age,
    String occupation,
    String zipCode,
    List<String> preferredGenres
) {}
```

- [ ] **Step 4: 创建 MovieCreateRequest**

```java
package com.rec.common.model.request;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Positive;
import java.util.List;

public record MovieCreateRequest(
    @NotBlank String title,
    String imdbId,
    Integer year,
    List<String> genres,
    String description,
    @Positive Integer runtimeMinutes,
    String titleType,
    Double imdbRating,
    Integer imdbVotes
) {}
```

- [ ] **Step 5: 创建 RatingCreateRequest**

```java
package com.rec.common.model.request;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;

public record RatingCreateRequest(
    @NotNull Long movieId,
    @NotNull @Min(1) @Max(10) Integer rating
) {}
```

- [ ] **Step 6: 创建 UserFeaturesRequest**

```java
package com.rec.common.model.request;

import java.util.List;

public record UserFeaturesRequest(
    Long userId,
    String gender,
    String age,
    String occupation,
    String zipCode,
    List<Long> histMovieIds,
    List<String> preferredGenres
) {}
```

- [ ] **Step 7: 验证编译**

```bash
mvn compile -pl recommend-common
```

Expected: BUILD SUCCESS

- [ ] **Step 8: 提交**

```bash
git add recommend-common/
git commit -m "feat: add request DTOs to common module"
```

---

### Task 3: Common — 响应 DTO (Record)

**Files:**
- Create: `recommend-common/src/main/java/com/rec/common/model/response/` 下 14 个文件

- [ ] **Step 1: 创建 TokenResponse**

```java
package com.rec.common.model.response;

import com.fasterxml.jackson.annotation.JsonProperty;

public record TokenResponse(
    @JsonProperty("access_token") String accessToken,
    @JsonProperty("token_type") String tokenType
) {
    public TokenResponse(String accessToken) {
        this(accessToken, "bearer");
    }
}
```

- [ ] **Step 2: 创建 UserProfileResponse**

```java
package com.rec.common.model.response;

import java.time.LocalDateTime;
import java.util.List;

public record UserProfileResponse(
    Long userId,
    String email,
    String username,
    String gender,
    String age,
    String occupation,
    String zipCode,
    Boolean isSuperuser,
    LocalDateTime createdAt,
    List<String> preferredGenres,
    List<String> frequentGenres,
    List<RatingResponse> recentRatings
) {}
```

- [ ] **Step 3: 创建 MovieDetailResponse**

```java
package com.rec.common.model.response;

import java.util.List;

public record MovieDetailResponse(
    Long movieId,
    String imdbId,
    String title,
    Integer year,
    List<String> genres,
    String description,
    Double avgRating,
    Integer ratingCount,
    Double imdbRating,
    Integer imdbVotes,
    Integer runtimeMinutes,
    String titleType
) {}
```

- [ ] **Step 4: 创建 MovieListItem + MovieListResponse**

```java
package com.rec.common.model.response;

import java.util.List;

public record MovieListItem(
    Long movieId,
    String title,
    Integer year,
    List<String> genres,
    Double avgRating,
    Double imdbRating
) {}

public record MovieListResponse(
    List<MovieListItem> items,
    long total,
    int page,
    int pageSize,
    boolean hasNext
) {}
```

- [ ] **Step 5: 创建 RatingResponse + UserRatingResponse**

```java
package com.rec.common.model.response;

public record RatingResponse(
    Long userId,
    Long movieId,
    Integer rating,
    Long timestamp
) {}

public record UserRatingResponse(
    Integer rating,
    boolean hasRated
) {}
```

- [ ] **Step 6: 创建推荐响应 DTO**

```java
package com.rec.common.model.response;

import java.util.List;

public record RecommendationItemResponse(
    Long movieId,
    String title,
    List<String> genres,
    Double score,
    Double recallScore,
    String recallType,
    String posterUrl
) {}

public record RecommendationResponse(
    List<RecommendationItemResponse> items,
    int recallCount,
    String rankingStrategy
) {}
```

- [ ] **Step 7: 创建人物相关 DTO**

```java
package com.rec.common.model.response;

import java.util.List;

public record PersonDetailResponse(
    String personId,
    String name,
    Integer birthYear,
    Integer deathYear,
    List<String> professions,
    List<String> knownForTitles
) {}

public record CastMemberResponse(
    String personId,
    String name,
    String character,
    String category,
    Integer ordering
) {}

public record MovieCastResponse(
    Long movieId,
    String movieTitle,
    List<CastMemberResponse> cast
) {}
```

- [ ] **Step 8: 创建 GenreListResponse**

```java
package com.rec.common.model.response;

import java.util.List;

public record GenreListResponse(List<String> genres) {}
```

- [ ] **Step 9: 创建 HealthResponse**

```java
package com.rec.common.model.response;

public record HealthResponse(
    String status,
    String version,
    String database,
    String redis,
    String elasticsearch
) {}
```

- [ ] **Step 10: 验证编译并提交**

```bash
mvn compile -pl recommend-common && \
git add recommend-common/ && \
git commit -m "feat: add response DTOs to common module"
```

---

### Task 4: Common — Pipeline 内部模型 + 异常 + 配置

**Files:**
- Create: `recommend-common/src/main/java/com/rec/common/model/pipeline/` 下 9 个 Record
- Create: `recommend-common/src/main/java/com/rec/common/exception/` 下 5 个 Exception 类
- Create: `recommend-common/src/main/java/com/rec/common/config/RecommendProperties.java`

- [ ] **Step 1: 创建管线 Record 模型**

```java
package com.rec.common.model.pipeline;

import java.util.List;

public record RecallItem(long movieId, double score, String recallType) {
    public RecallItem withScore(double newScore) {
        return new RecallItem(movieId, newScore, recallType);
    }
}

public record RankedItem(
    long movieId, double score, double recallScore, String recallType,
    List<String> genres, int year
) {}

public record RecommendationItem(long movieId, double score, String recallType) {}

public record ItemFeatures(String genre, List<String> genresList, int isAdult, int year) {}

public record CTRPrediction(long movieId, float ctrScore) {}

public record UserVectorResponse(List<Double> userVector, String version) {}

public record RankingRequest(
    java.util.Map<String, Object> userFeatures,
    java.util.List<java.util.Map<String, Object>> itemFeatures,
    String modelVersion
) {}

public record RecallRequest(
    java.util.Map<String, Object> userFeatures,
    java.util.List<Long> histMovieIds,
    String modelVersion
) {}

public record ModelVersion(String modelType, String version, String deployTime) {}
```

- [ ] **Step 2: 创建异常类**

```java
package com.rec.common.exception;

public class RecommendationException extends RuntimeException {
    public RecommendationException(String message) { super(message); }
    public RecommendationException(String message, Throwable cause) { super(message, cause); }
}

public class InferenceException extends RecommendationException {
    public InferenceException(String message) { super(message); }
}

public class StrategyExecutionException extends RecommendationException {
    public StrategyExecutionException(String message, Throwable cause) { super(message, cause); }
}

public class DataAccessException extends RuntimeException {
    public DataAccessException(String message, Throwable cause) { super(message, cause); }
}

public class AuthException extends RuntimeException {
    public AuthException(String message) { super(message); }
}
```

- [ ] **Step 3: 创建 RecommendProperties**

```java
package com.rec.common.config;

import org.springframework.boot.context.properties.ConfigurationProperties;
import java.util.Map;

@ConfigurationProperties(prefix = "recommend")
public record RecommendProperties(
    Rpc rpc,
    Strategy strategy
) {
    public record Rpc(String client, Inference inference) {
        public record Inference(String baseUrl, int connectTimeout, int readTimeout, int maxRetries) {}
    }

    public record Strategy(
        Map<String, Map<String, Boolean>> recall,
        Map<String, Map<String, Boolean>> ranking,
        Map<String, Map<String, Boolean>> reranking,
        Map<String, Map<String, Boolean>> coldstart
    ) {}
}
```

- [ ] **Step 4: 验证编译并提交**

```bash
mvn compile -pl recommend-common && \
git add recommend-common/ && \
git commit -m "feat: add pipeline models, exceptions, and config properties"
```

---

### Task 5: Repository — 9 个 JPA Entity

**Files:**
- Create: `recommend-repository/src/main/java/com/rec/repository/entity/` 下 9 个 Entity
- Create: `recommend-repository/src/main/java/com/rec/repository/config/ArrayTypeHandler.java`

- [ ] **Step 1: 创建 ArrayTypeHandler**

```java
package com.rec.repository.config;

import org.apache.ibatis.type.BaseTypeHandler;
import org.apache.ibatis.type.JdbcType;
import org.apache.ibatis.type.MappedTypes;
import java.sql.*;

@MappedTypes(String[].class)
public class ArrayTypeHandler extends BaseTypeHandler<String[]> {

    @Override
    public void setNonNullParameter(PreparedStatement ps, int i, String[] parameter, JdbcType jdbcType)
            throws SQLException {
        ps.setArray(i, ps.getConnection().createArrayOf("text", parameter));
    }

    @Override
    public String[] getNullableResult(ResultSet rs, String columnName) throws SQLException {
        Array array = rs.getArray(columnName);
        return array != null ? (String[]) array.getArray() : null;
    }

    @Override
    public String[] getNullableResult(ResultSet rs, int columnIndex) throws SQLException {
        Array array = rs.getArray(columnIndex);
        return array != null ? (String[]) array.getArray() : null;
    }

    @Override
    public String[] getNullableResult(CallableStatement cs, int columnIndex) throws SQLException {
        Array array = cs.getArray(columnIndex);
        return array != null ? (String[]) array.getArray() : null;
    }
}
```

- [ ] **Step 2: 创建核心 Entity (User, Movie, Rating)**

```java
package com.rec.repository.entity;

import com.baomidou.mybatisplus.annotation.*;
import com.rec.repository.config.ArrayTypeHandler;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("users")
public class UserEntity {
    @TableId(type = IdType.AUTO)
    private Long userId;
    private String email;
    private String username;
    private String hashedPassword;
    private Integer isActive;
    private Integer isSuperuser;
    private String gender;
    private String age;
    private String occupation;
    private String zipCode;
    private LocalDateTime createdAt;

    @TableField(typeHandler = ArrayTypeHandler.class)
    private String[] preferredGenres;
}

@Data
@TableName("movies")
public class MovieEntity {
    @TableId(type = IdType.AUTO)
    private Long movieId;
    private String imdbId;
    private String title;
    private Integer year;

    @TableField(typeHandler = ArrayTypeHandler.class)
    private String[] genres;

    private String description;
    private Double avgRating;
    private Integer ratingCount;
    private Double imdbRating;
    private Integer imdbVotes;
    private String titleType;
    private Integer runtimeMinutes;
    private Integer isAdult;
    private Long createdBy;
}

@Data
@TableName("ratings")
public class RatingEntity {
    private Long userId;
    private Long movieId;
    private Integer rating;
    private Long timestamp;
}
```

- [ ] **Step 3: 创建 Genre + IMDb Entity (6 个)**

```java
package com.rec.repository.entity;

import com.baomidou.mybatisplus.annotation.*;
import com.rec.repository.config.ArrayTypeHandler;
import lombok.Data;

@Data
@TableName("genres")
public class GenreEntity {
    @TableId(type = IdType.AUTO)
    private Long id;
    private String name;
}

@Data
@TableName("title_ratings")
public class TitleRatingEntity {
    private String tconst;
    private Double averageRating;
    private Integer numVotes;
}

@Data
@TableName("name_basics")
public class NameBasicsEntity {
    private String nconst;
    private String primaryName;
    private Integer birthYear;
    private Integer deathYear;

    @TableField(typeHandler = ArrayTypeHandler.class)
    private String[] primaryProfession;

    @TableField(typeHandler = ArrayTypeHandler.class)
    private String[] knownForTitles;
}

@Data
@TableName("title_crew")
public class TitleCrewEntity {
    private String tconst;

    @TableField(typeHandler = ArrayTypeHandler.class)
    private String[] directors;

    @TableField(typeHandler = ArrayTypeHandler.class)
    private String[] writers;
}

@Data
@TableName("title_principals")
public class TitlePrincipalEntity {
    private String tconst;
    private Integer ordering;
    private String nconst;
    private String category;
    private String job;
    private String characters;
}

@Data
@TableName("title_akas")
public class TitleAkaEntity {
    private String tconst;
    private Integer ordering;
    private String title;
    private String region;
    private String language;
    private String types;
    private String attributes;
    private Integer isOriginalTitle;
}
```

- [ ] **Step 4: 验证编译并提交**

```bash
mvn compile -pl recommend-repository && \
git add recommend-repository/ && \
git commit -m "feat: add JPA entities with PG ARRAY type handler"
```

---

### Task 6: Repository — 9 个 MyBatis-Plus Mapper

**Files:**
- Create: `recommend-repository/src/main/java/com/rec/repository/mapper/` 下 9 个 Mapper 接口

- [ ] **Step 1: 创建 UserMapper**

```java
package com.rec.repository.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.rec.repository.entity.UserEntity;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

@Mapper
public interface UserMapper extends BaseMapper<UserEntity> {

    @Select("SELECT * FROM users WHERE email = #{email} AND is_active = 1")
    UserEntity findByEmail(@Param("email") String email);

    @Select("SELECT * FROM users WHERE user_id = #{userId} AND is_active = 1")
    UserEntity findActiveById(@Param("userId") Long userId);
}
```

- [ ] **Step 2: 创建 MovieMapper**

```java
package com.rec.repository.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.rec.repository.entity.MovieEntity;
import org.apache.ibatis.annotations.*;

import java.util.List;

@Mapper
public interface MovieMapper extends BaseMapper<MovieEntity> {

    @Select("SELECT * FROM movies ORDER BY avg_rating DESC, rating_count DESC LIMIT #{limit}")
    List<MovieEntity> findPopular(@Param("limit") int limit);

    @Select("SELECT * FROM movies WHERE ${genreFilter} ORDER BY year DESC, avg_rating DESC LIMIT #{limit}")
    List<MovieEntity> findByGenreFilter(@Param("genreFilter") String genreFilter,
                                        @Param("limit") int limit);

    @Select("SELECT * FROM movies WHERE genres && ARRAY[#{genre}]::text[] " +
            "AND avg_rating >= 5 ORDER BY year DESC, avg_rating DESC LIMIT #{limit}")
    List<MovieEntity> findByGenre(@Param("genre") String genre, @Param("limit") int limit);

    default String buildGenreFilter(List<String> genres) {
        if (genres == null || genres.isEmpty()) return "1=1";
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < genres.size(); i++) {
            if (i > 0) sb.append(" OR ");
            sb.append("genres && ARRAY['").append(genres.get(i)).append("']::text[]");
        }
        return sb.toString();
    }
}
```

- [ ] **Step 3: 创建 RatingMapper**

```java
package com.rec.repository.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.rec.repository.entity.RatingEntity;
import org.apache.ibatis.annotations.*;

import java.util.List;

@Mapper
public interface RatingMapper extends BaseMapper<RatingEntity> {

    @Select("SELECT * FROM ratings WHERE user_id = #{userId} AND movie_id = #{movieId}")
    RatingEntity findByUserAndMovie(@Param("userId") Long userId, @Param("movieId") Long movieId);

    @Select("SELECT * FROM ratings WHERE user_id = #{userId} ORDER BY timestamp DESC LIMIT #{limit}")
    List<RatingEntity> findRecentByUser(@Param("userId") Long userId, @Param("limit") int limit);

    @Select("SELECT COUNT(*) FROM ratings WHERE user_id = #{userId}")
    int countByUser(@Param("userId") Long userId);

    @Delete("DELETE FROM ratings WHERE user_id = #{userId} AND movie_id = #{movieId}")
    int deleteByUserAndMovie(@Param("userId") Long userId, @Param("movieId") Long movieId);
}
```

- [ ] **Step 4: 创建其余 6 个 Mapper**

```java
package com.rec.repository.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.rec.repository.entity.*;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import java.util.List;

@Mapper
public interface GenreMapper extends BaseMapper<GenreEntity> {
    @Select("SELECT name FROM genres ORDER BY name")
    List<String> findAllNames();
}

@Mapper
public interface TitleRatingMapper extends BaseMapper<TitleRatingEntity> {}

@Mapper
public interface NameBasicsMapper extends BaseMapper<NameBasicsEntity> {
    @Select("SELECT * FROM name_basics WHERE nconst = #{nconst}")
    NameBasicsEntity findByNconst(@Param("nconst") String nconst);
}

@Mapper
public interface TitleCrewMapper extends BaseMapper<TitleCrewEntity> {
    @Select("SELECT * FROM title_crew WHERE tconst = #{tconst}")
    TitleCrewEntity findByTconst(@Param("tconst") String tconst);
}

@Mapper
public interface TitlePrincipalMapper extends BaseMapper<TitlePrincipalEntity> {
    @Select("SELECT * FROM title_principals WHERE tconst = #{tconst} ORDER BY ordering")
    List<TitlePrincipalEntity> findByTconst(@Param("tconst") String tconst);
}

@Mapper
public interface TitleAkaMapper extends BaseMapper<TitleAkaEntity> {}
```

- [ ] **Step 5: 验证编译并提交**

```bash
mvn compile -pl recommend-repository && \
git add recommend-repository/ && \
git commit -m "feat: add MyBatis-Plus mapper interfaces"
```

---

### Task 7: Repository — Redis + ES Repository

**Files:**
- Create: `recommend-repository/src/main/java/com/rec/repository/redis/UserProfileRedisRepository.java`
- Create: `recommend-repository/src/main/java/com/rec/repository/es/MovieSearchRepository.java`

- [ ] **Step 1: 创建 UserProfileRedisRepository**

```java
package com.rec.repository.redis;

import org.springframework.data.redis.core.ReactiveRedisTemplate;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;

import java.util.*;

@Component
public class UserProfileRedisRepository {

    private final ReactiveRedisTemplate<String, String> redis;

    public UserProfileRedisRepository(ReactiveRedisTemplate<String, String> redis) {
        this.redis = redis;
    }

    // ===== 读取 =====

    public Mono<Map<String, String>> getUserProfile(Long userId) {
        return redis.<String, String>opsForHash()
            .entries("user:" + userId + ":profile")
            .collectMap(Map.Entry::getKey, e -> String.valueOf(e.getValue()))
            .defaultIfEmpty(Collections.emptyMap());
    }

    public Mono<List<Long>> getUserHistory(Long userId, int maxLen) {
        return redis.opsForList()
            .range("user:" + userId + ":history", 0, maxLen - 1)
            .map(Long::parseLong)
            .collectList();
    }

    public Mono<Map<String, Map<String, Integer>>> getUCBStats(Long userId) {
        return redis.<String, String>opsForHash()
            .entries("user:" + userId + ":genre_ucb")
            .collectMap(Map.Entry::getKey, e -> {
                String[] parts = e.getValue().toString().split(":");
                Map<String, Integer> stat = new HashMap<>();
                stat.put("n", Integer.parseInt(parts[0]));
                stat.put("reward", Integer.parseInt(parts[1]));
                return stat;
            });
    }

    // ===== 写入 =====

    public Mono<Long> pushUserHistory(Long userId, Long movieId) {
        return redis.opsForList().leftPush("user:" + userId + ":history", movieId.toString());
    }

    public Mono<Void> updateUserProfile(Long userId, Map<String, String> profile) {
        return redis.opsForHash()
            .putAll("user:" + userId + ":profile", profile)
            .then();
    }

    public Mono<Void> updateUCBStats(Long userId, String genre, int reward) {
        String key = "user:" + userId + ":genre_ucb";
        return redis.opsForHash().increment(key, genre + ":n", 1)
            .then(redis.opsForHash().increment(key, genre + ":reward", reward))
            .then();
    }
}
```

- [ ] **Step 2: 创建 MovieSearchRepository**

```java
package com.rec.repository.es;

import org.springframework.data.elasticsearch.client.elc.ReactiveElasticsearchClient;
import org.springframework.data.elasticsearch.core.ReactiveElasticsearchOperations;
import org.springframework.data.elasticsearch.core.query.Criteria;
import org.springframework.data.elasticsearch.core.query.CriteriaQuery;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

import java.util.List;

@Component
public class MovieSearchRepository {

    private final ReactiveElasticsearchOperations es;

    public MovieSearchRepository(ReactiveElasticsearchOperations es) {
        this.es = es;
    }

    public Flux<MovieSearchResult> searchByGenres(List<String> genres, int topK) {
        // terms query on genres.keyword, filter avg_rating >= 5,
        // sort by year desc, avg_rating desc
        Criteria criteria = new Criteria("genres").in(genres)
            .and(new Criteria("avg_rating").greaterThanEqual(5));
        var query = new CriteriaQuery(criteria).setMaxResults(topK);
        return es.search(query, MovieSearchResult.class)
            .map(hit -> hit.getContent());
    }

    public Flux<MovieSearchResult> searchByKeyword(String keyword, int from, int size) {
        Criteria criteria = new Criteria("title").matches(keyword)
            .or(new Criteria("description").matches(keyword));
        var query = new CriteriaQuery(criteria)
            .setFrom(from)
            .setMaxResults(size);
        return es.search(query, MovieSearchResult.class)
            .map(hit -> hit.getContent());
    }

    public Flux<MovieSearchResult> suggest(String prefix, int limit) {
        // completion suggest on title field
        Criteria criteria = new Criteria("title").startsWith(prefix);
        var query = new CriteriaQuery(criteria).setMaxResults(limit);
        return es.search(query, MovieSearchResult.class)
            .map(hit -> hit.getContent());
    }
}
```

- [ ] **Step 3: 创建 MovieSearchResult DTO (放在 repository 模块)**

```java
package com.rec.repository.es;

import org.springframework.data.elasticsearch.annotations.Document;

import java.util.List;

@Document(indexName = "movies")
public record MovieSearchResult(
    Long movieId,
    String title,
    Integer year,
    List<String> genres,
    Double avgRating,
    Integer ratingCount,
    Double imdbRating,
    Integer imdbVotes,
    String description
) {}
```

- [ ] **Step 4: 验证编译并提交**

```bash
mvn compile -pl recommend-repository && \
git add recommend-repository/ && \
git commit -m "feat: add Redis and Elasticsearch repositories"
```

---

### Task 8: RPC — ModelInferenceClient 接口 + HTTP 实现

**Files:**
- Create: `recommend-rpc/src/main/java/com/rec/rpc/ModelInferenceClient.java`
- Create: `recommend-rpc/src/main/java/com/rec/rpc/HttpModelInferenceClient.java`

- [ ] **Step 1: 创建接口**

```java
package com.rec.rpc;

import com.rec.common.model.pipeline.*;
import reactor.core.publisher.Mono;

import java.util.List;

public interface ModelInferenceClient {

    Mono<List<CTRPrediction>> predictCTR(RankingRequest request);

    Mono<UserVectorResponse> generateUserVector(RecallRequest request);

    Mono<Boolean> health();

    Mono<ModelVersion> getVersion(String modelType);
}
```

- [ ] **Step 2: 创建 HTTP 实现**

```java
package com.rec.rpc;

import com.rec.common.exception.InferenceException;
import com.rec.common.model.pipeline.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.time.Duration;
import java.util.List;

@Component
@ConditionalOnProperty(name = "recommend.rpc.client", havingValue = "http", matchIfMissing = true)
public class HttpModelInferenceClient implements ModelInferenceClient {

    private final WebClient webClient;

    public HttpModelInferenceClient(
        @Value("${recommend.rpc.inference.base-url}") String baseUrl,
        @Value("${recommend.rpc.inference.read-timeout:2000}") int readTimeout
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
                r -> r.bodyToMono(String.class)
                    .flatMap(msg -> Mono.error(new InferenceException("Model service error: " + msg))))
            .bodyToMono(new ParameterizedTypeReference<List<CTRPrediction>>() {})
            .timeout(Duration.ofMillis(2000));
    }

    @Override
    public Mono<UserVectorResponse> generateUserVector(RecallRequest request) {
        return webClient.post()
            .uri("/api/predict/recall")
            .bodyValue(request)
            .retrieve()
            .onStatus(s -> s.is5xxServerError(),
                r -> r.bodyToMono(String.class)
                    .flatMap(msg -> Mono.error(new InferenceException("Model service error: " + msg))))
            .bodyToMono(UserVectorResponse.class)
            .timeout(Duration.ofMillis(2000));
    }

    @Override
    public Mono<Boolean> health() {
        return webClient.get()
            .uri("/api/health")
            .retrieve()
            .bodyToMono(String.class)
            .map(r -> r.contains("healthy"))
            .onErrorReturn(false);
    }

    @Override
    public Mono<ModelVersion> getVersion(String modelType) {
        return webClient.get()
            .uri("/api/version/" + modelType)
            .retrieve()
            .bodyToMono(ModelVersion.class);
    }
}
```

- [ ] **Step 3: 验证编译并提交**

```bash
mvn compile -pl recommend-rpc && \
git add recommend-rpc/ && \
git commit -m "feat: add RPC client interface and HTTP implementation"
```

---

### Task 9: Strategy — 召回接口 + 3 个实现

**Files:**
- Create: `recommend-strategy/src/main/java/com/rec/strategy/recall/RecallStrategy.java`
- Create: `recommend-strategy/src/main/java/com/rec/strategy/recall/UserPreferenceRecallStrategy.java`
- Create: `recommend-strategy/src/main/java/com/rec/strategy/recall/YouTubeDNNRecallStrategy.java`
- Create: `recommend-strategy/src/main/java/com/rec/strategy/recall/ItemEmbeddingRecallStrategy.java`

- [ ] **Step 1: 创建 RecallStrategy 接口**

```java
package com.rec.strategy.recall;

import com.rec.common.model.pipeline.RecallItem;
import reactor.core.publisher.Mono;

import java.util.List;
import java.util.Map;

public interface RecallStrategy {
    String getName();
    Mono<List<RecallItem>> recall(Map<String, Object> userFeatures, int topK);
}
```

- [ ] **Step 2: 创建 UserPreferenceRecallStrategy**

```java
package com.rec.strategy.recall;

import com.rec.common.model.pipeline.RecallItem;
import com.rec.repository.es.MovieSearchRepository;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;

import java.util.List;
import java.util.Map;

@Component
@ConditionalOnProperty(name = "recommend.strategy.recall.user-preference.enabled",
                       havingValue = "true", matchIfMissing = true)
public class UserPreferenceRecallStrategy implements RecallStrategy {

    private final MovieSearchRepository esRepo;

    public UserPreferenceRecallStrategy(MovieSearchRepository esRepo) {
        this.esRepo = esRepo;
    }

    @Override
    public String getName() {
        return "user_preference";
    }

    @Override
    @SuppressWarnings("unchecked")
    public Mono<List<RecallItem>> recall(Map<String, Object> userFeatures, int topK) {
        List<String> genres = (List<String>) userFeatures.getOrDefault("frequent_genres", List.of());
        if (genres.isEmpty()) {
            return Mono.just(List.of());
        }
        return esRepo.searchByGenres(genres, topK)
            .map(r -> new RecallItem(r.movieId(), 0.8, getName()))
            .collectList();
    }
}
```

- [ ] **Step 3: 创建 YouTubeDNNRecallStrategy**

```java
package com.rec.strategy.recall;

import com.rec.common.model.pipeline.RecallItem;
import com.rec.common.model.pipeline.RecallRequest;
import com.rec.rpc.ModelInferenceClient;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;

import java.util.List;
import java.util.Map;

@Component
@ConditionalOnProperty(name = "recommend.strategy.recall.youtubednn.enabled",
                       havingValue = "true", matchIfMissing = false)
public class YouTubeDNNRecallStrategy implements RecallStrategy {

    private final ModelInferenceClient rpcClient;

    public YouTubeDNNRecallStrategy(ModelInferenceClient rpcClient) {
        this.rpcClient = rpcClient;
    }

    @Override
    public String getName() {
        return "youtubednn";
    }

    @Override
    @SuppressWarnings("unchecked")
    public Mono<List<RecallItem>> recall(Map<String, Object> userFeatures, int topK) {
        var request = new RecallRequest(
            userFeatures,
            (List<Long>) userFeatures.getOrDefault("histMovieIds", List.of()),
            null
        );
        return rpcClient.generateUserVector(request)
            .flatMapMany(userVector -> {
                // 用 user embedding 与本地 item embeddings 做余弦相似度检索
                // 此处为简化实现，实际需加载 item_embeddings.npy
                return Mono.empty();
            })
            .map(item -> new RecallItem(item.movieId(), item.score(), getName()))
            .collectList()
            .switchIfEmpty(Mono.just(List.of()));
    }
}
```

- [ ] **Step 4: 创建 ItemEmbeddingRecallStrategy**

```java
package com.rec.strategy.recall;

import com.rec.common.model.pipeline.RecallItem;
import com.rec.common.model.pipeline.RecallRequest;
import com.rec.rpc.ModelInferenceClient;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;

import java.util.List;
import java.util.Map;

@Component
@ConditionalOnProperty(name = "recommend.strategy.recall.item-embedding.enabled",
                       havingValue = "true", matchIfMissing = false)
public class ItemEmbeddingRecallStrategy implements RecallStrategy {

    private final ModelInferenceClient rpcClient;

    public ItemEmbeddingRecallStrategy(ModelInferenceClient rpcClient) {
        this.rpcClient = rpcClient;
    }

    @Override
    public String getName() {
        return "item_embedding";
    }

    @Override
    @SuppressWarnings("unchecked")
    public Mono<List<RecallItem>> recall(Map<String, Object> userFeatures, int topK) {
        var request = new RecallRequest(
            userFeatures,
            (List<Long>) userFeatures.getOrDefault("histMovieIds", List.of()),
            null
        );
        return rpcClient.generateUserVector(request)
            .flatMapMany(userVector -> Mono.empty())
            .map(item -> new RecallItem(item.movieId(), item.score(), getName()))
            .collectList()
            .switchIfEmpty(Mono.just(List.of()));
    }
}
```

- [ ] **Step 5: 验证编译并提交**

```bash
mvn compile -pl recommend-strategy && \
git add recommend-strategy/ && \
git commit -m "feat: add recall strategy interface and 3 implementations"
```

---

### Task 10: Strategy — 排序接口 + 2 个实现

**Files:**
- Create: `recommend-strategy/src/main/java/com/rec/strategy/ranking/RankingStrategy.java`
- Create: `recommend-strategy/src/main/java/com/rec/strategy/ranking/DeepFMRankingStrategy.java`
- Create: `recommend-strategy/src/main/java/com/rec/strategy/ranking/FallbackRankingStrategy.java`

- [ ] **Step 1: 创建 RankingStrategy 接口**

```java
package com.rec.strategy.ranking;

import com.rec.common.model.pipeline.RankedItem;
import com.rec.common.model.pipeline.RecallItem;
import com.rec.common.model.pipeline.ItemFeatures;
import reactor.core.publisher.Mono;

import java.util.List;
import java.util.Map;

public interface RankingStrategy {
    String getName();
    Mono<List<RankedItem>> rank(List<RecallItem> candidates,
                                Map<String, Object> userFeatures,
                                Map<Long, ItemFeatures> itemFeaturesMap);
}
```

- [ ] **Step 2: 创建 DeepFMRankingStrategy**

```java
package com.rec.strategy.ranking;

import com.rec.common.model.pipeline.*;
import com.rec.rpc.ModelInferenceClient;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;

import java.util.*;
import java.util.stream.Collectors;

@Component
@ConditionalOnProperty(name = "recommend.strategy.ranking.deepfm.enabled",
                       havingValue = "true", matchIfMissing = true)
public class DeepFMRankingStrategy implements RankingStrategy {

    private final ModelInferenceClient rpcClient;

    public DeepFMRankingStrategy(ModelInferenceClient rpcClient) {
        this.rpcClient = rpcClient;
    }

    @Override
    public String getName() {
        return "deepfm";
    }

    @Override
    public Mono<List<RankedItem>> rank(List<RecallItem> candidates,
                                       Map<String, Object> userFeatures,
                                       Map<Long, ItemFeatures> itemFeaturesMap) {

        List<Map<String, Object>> itemFeatureList = candidates.stream()
            .map(c -> {
                ItemFeatures feats = itemFeaturesMap.get(c.movieId());
                Map<String, Object> feat = new HashMap<>();
                feat.put("movie_id", c.movieId());
                feat.put("genres", feats != null ? feats.genre() : null);
                feat.put("isAdult", feats != null ? feats.isAdult() : 0);
                return feat;
            })
            .collect(Collectors.toList());

        var request = new RankingRequest(userFeatures, itemFeatureList, null);

        return rpcClient.predictCTR(request)
            .map(predictions -> {
                Map<Long, Float> ctrMap = predictions.stream()
                    .collect(Collectors.toMap(CTRPrediction::movieId, CTRPrediction::ctrScore));
                return candidates.stream()
                    .map(c -> {
                        ItemFeatures feats = itemFeaturesMap.get(c.movieId());
                        float ctr = ctrMap.getOrDefault(c.movieId(), (float) c.score());
                        return new RankedItem(
                            c.movieId(), ctr, c.score(), c.recallType(),
                            feats != null ? feats.genresList() : List.of(),
                            feats != null ? feats.year() : 0
                        );
                    })
                    .sorted(Comparator.comparingDouble(RankedItem::score).reversed())
                    .collect(Collectors.toList());
            });
    }
}
```

- [ ] **Step 3: 创建 FallbackRankingStrategy**

```java
package com.rec.strategy.ranking;

import com.rec.common.model.pipeline.*;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;

import java.util.*;
import java.util.stream.Collectors;

@Component
@ConditionalOnProperty(name = "recommend.strategy.ranking.fallback.enabled",
                       havingValue = "true", matchIfMissing = true)
public class FallbackRankingStrategy implements RankingStrategy {

    @Override
    public String getName() {
        return "fallback";
    }

    @Override
    public Mono<List<RankedItem>> rank(List<RecallItem> candidates,
                                       Map<String, Object> userFeatures,
                                       Map<Long, ItemFeatures> itemFeaturesMap) {
        return Mono.just(
            candidates.stream()
                .map(c -> {
                    ItemFeatures feats = itemFeaturesMap.get(c.movieId());
                    return new RankedItem(
                        c.movieId(), c.score(), c.score(), c.recallType(),
                        feats != null ? feats.genresList() : List.of(),
                        feats != null ? feats.year() : 0
                    );
                })
                .sorted(Comparator.comparingDouble(RankedItem::score).reversed())
                .collect(Collectors.toList())
        );
    }
}
```

- [ ] **Step 4: 验证编译并提交**

```bash
mvn compile -pl recommend-strategy && \
git add recommend-strategy/ && \
git commit -m "feat: add ranking strategy interface and DeepFM + Fallback implementations"
```

---

### Task 11: Strategy — 重排接口 + 冷启动接口及 5 个实现

**Files:**
- Create: `recommend-strategy/src/main/java/com/rec/strategy/reranking/RerankingStrategy.java`
- Create: `recommend-strategy/src/main/java/com/rec/strategy/reranking/GenreDispersionStrategy.java`
- Create: `recommend-strategy/src/main/java/com/rec/strategy/reranking/DecadeDispersionStrategy.java`
- Create: `recommend-strategy/src/main/java/com/rec/strategy/coldstart/ColdStartStrategy.java`
- Create: `recommend-strategy/src/main/java/com/rec/strategy/coldstart/UCBGenreStrategy.java`
- Create: `recommend-strategy/src/main/java/com/rec/strategy/coldstart/PreferredGenreStrategy.java`
- Create: `recommend-strategy/src/main/java/com/rec/strategy/coldstart/PopularRecentStrategy.java`

- [ ] **Step 1: 创建 RerankingStrategy 接口**

```java
package com.rec.strategy.reranking;

import com.rec.common.model.pipeline.RankedItem;
import reactor.core.publisher.Mono;

import java.util.List;
import java.util.Map;

public interface RerankingStrategy {
    String getName();
    Mono<List<RankedItem>> rerank(List<RankedItem> items, Map<String, Object> userFeatures);
}
```

- [ ] **Step 2: 创建 GenreDispersionStrategy**

```java
package com.rec.strategy.reranking;

import com.rec.common.model.pipeline.RankedItem;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;

import java.util.*;

@Component
@ConditionalOnProperty(name = "recommend.strategy.reranking.genre-dispersion.enabled",
                       havingValue = "true", matchIfMissing = true)
public class GenreDispersionStrategy implements RerankingStrategy {

    @Override
    public String getName() {
        return "genre_dispersion";
    }

    @Override
    public Mono<List<RankedItem>> rerank(List<RankedItem> items, Map<String, Object> userFeatures) {
        List<RankedItem> result = new ArrayList<>(items);
        List<RankedItem> deferred = new ArrayList<>();

        for (int i = 0; i < result.size(); i++) {
            if (sameGenreCount(result, i) >= 2) {
                deferred.add(result.remove(i));
                i--;
            }
        }
        result.addAll(deferred);
        return Mono.just(result);
    }

    private int sameGenreCount(List<RankedItem> items, int pos) {
        if (pos < 1) return 0;
        var current = items.get(pos).genres();
        int count = 0;
        for (int i = pos - 1; i >= 0 && i >= pos - 2; i--) {
            if (!Collections.disjoint(current, items.get(i).genres())) {
                count++;
            } else break;
        }
        return count;
    }
}
```

- [ ] **Step 3: 创建 DecadeDispersionStrategy**

```java
package com.rec.strategy.reranking;

import com.rec.common.model.pipeline.RankedItem;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;

import java.util.*;

@Component
@ConditionalOnProperty(name = "recommend.strategy.reranking.decade-dispersion.enabled",
                       havingValue = "true", matchIfMissing = true)
public class DecadeDispersionStrategy implements RerankingStrategy {

    @Override
    public String getName() {
        return "decade_dispersion";
    }

    @Override
    public Mono<List<RankedItem>> rerank(List<RankedItem> items, Map<String, Object> userFeatures) {
        List<RankedItem> result = new ArrayList<>(items);
        List<RankedItem> deferred = new ArrayList<>();

        for (int i = 0; i < result.size(); i++) {
            if (sameDecadeCount(result, i) >= 2) {
                deferred.add(result.remove(i));
                i--;
            }
        }
        result.addAll(deferred);
        return Mono.just(result);
    }

    private int sameDecadeCount(List<RankedItem> items, int pos) {
        if (pos < 1) return 0;
        int currentDecade = items.get(pos).year() / 10;
        int count = 0;
        for (int i = pos - 1; i >= 0 && i >= pos - 2; i--) {
            if (items.get(i).year() / 10 == currentDecade) {
                count++;
            } else break;
        }
        return count;
    }
}
```

- [ ] **Step 4: 创建 ColdStartStrategy 接口**

```java
package com.rec.strategy.coldstart;

import com.rec.common.model.pipeline.RecallItem;
import reactor.core.publisher.Mono;

import java.util.List;
import java.util.Map;

public interface ColdStartStrategy {
    String getName();
    boolean canHandle(Map<String, Object> userFeatures);
    int getWeight();
    Mono<List<RecallItem>> recommend(Map<String, Object> userFeatures, int topK);
}
```

- [ ] **Step 5: 创建 3 个冷启动实现**

```java
package com.rec.strategy.coldstart;

import com.rec.common.model.pipeline.RecallItem;
import com.rec.repository.es.MovieSearchRepository;
import com.rec.repository.redis.UserProfileRedisRepository;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;

import java.util.List;
import java.util.Map;

@Component
@ConditionalOnProperty(name = "recommend.strategy.coldstart.ucb-genre.enabled",
                       havingValue = "true", matchIfMissing = true)
public class UCBGenreStrategy implements ColdStartStrategy {

    private final UserProfileRedisRepository redisRepo;
    private final MovieSearchRepository esRepo;

    public UCBGenreStrategy(UserProfileRedisRepository redisRepo, MovieSearchRepository esRepo) {
        this.redisRepo = redisRepo;
        this.esRepo = esRepo;
    }

    @Override public String getName() { return "ucb_genre"; }
    @Override public boolean canHandle(Map<String, Object> f) { return true; }
    @Override public int getWeight() { return 70; }

    @Override
    public Mono<List<RecallItem>> recommend(Map<String, Object> userFeatures, int topK) {
        Long userId = (Long) userFeatures.get("userId");
        return redisRepo.getUCBStats(userId)
            .flatMap(stats -> {
                // 选 UCB 值最高的 genre
                String bestGenre = selectBestGenre(stats);
                return esRepo.searchByGenres(List.of(bestGenre), topK)
                    .map(r -> new RecallItem(r.movieId(), 1.0, getName()))
                    .collectList();
            })
            .switchIfEmpty(
                esRepo.searchByGenres(List.of(), topK)
                    .map(r -> new RecallItem(r.movieId(), 1.0, getName()))
                    .collectList()
            );
    }

    private String selectBestGenre(Map<String, Map<String, Integer>> stats) {
        return stats.entrySet().stream()
            .max((a, b) -> {
                double ucbA = ucb(a.getValue().get("n"), a.getValue().get("reward"));
                double ucbB = ucb(b.getValue().get("n"), b.getValue().get("reward"));
                return Double.compare(ucbA, ucbB);
            })
            .map(Map.Entry::getKey)
            .orElse("Action");
    }

    private double ucb(int n, int reward) {
        if (n == 0) return Double.MAX_VALUE;
        return (double) reward / n + Math.sqrt(2 * Math.log(100) / n);
    }
}

@Component
@ConditionalOnProperty(name = "recommend.strategy.coldstart.preferred-genre.enabled",
                       havingValue = "true", matchIfMissing = true)
class PreferredGenreStrategy implements ColdStartStrategy {

    private final MovieSearchRepository esRepo;

    public PreferredGenreStrategy(MovieSearchRepository esRepo) {
        this.esRepo = esRepo;
    }

    @Override public String getName() { return "preferred_genre"; }
    @Override public boolean canHandle(Map<String, Object> f) { return true; }
    @Override public int getWeight() { return 10; }

    @Override
    @SuppressWarnings("unchecked")
    public Mono<List<RecallItem>> recommend(Map<String, Object> userFeatures, int topK) {
        List<String> genres = (List<String>) userFeatures.getOrDefault("preferredGenres", List.of());
        return esRepo.searchByGenres(genres, topK)
            .map(r -> new RecallItem(r.movieId(), 0.9, getName()))
            .collectList();
    }
}

@Component
@ConditionalOnProperty(name = "recommend.strategy.coldstart.popular-recent.enabled",
                       havingValue = "true", matchIfMissing = true)
class PopularRecentStrategy implements ColdStartStrategy {

    private final MovieSearchRepository esRepo;

    public PopularRecentStrategy(MovieSearchRepository esRepo) {
        this.esRepo = esRepo;
    }

    @Override public String getName() { return "popular_recent"; }
    @Override public boolean canHandle(Map<String, Object> f) { return true; }
    @Override public int getWeight() { return 20; }

    @Override
    public Mono<List<RecallItem>> recommend(Map<String, Object> userFeatures, int topK) {
        return esRepo.searchByGenres(List.of(), topK)
            .map(r -> new RecallItem(r.movieId(), 0.7, getName()))
            .collectList();
    }
}
```

- [ ] **Step 6: 验证编译并提交**

```bash
mvn compile -pl recommend-strategy && \
git add recommend-strategy/ && \
git commit -m "feat: add reranking and coldstart strategy interfaces and implementations"
```

---

### Task 12: Strategy — 4 个 Registry 收集器

**Files:**
- Create: `recommend-strategy/src/main/java/com/rec/strategy/registry/RecallStrategyRegistry.java`
- Create: `recommend-strategy/src/main/java/com/rec/strategy/registry/RankingStrategyRegistry.java`
- Create: `recommend-strategy/src/main/java/com/rec/strategy/registry/RerankingStrategyRegistry.java`
- Create: `recommend-strategy/src/main/java/com/rec/strategy/registry/ColdStartStrategyRegistry.java`

- [ ] **Step 1: 创建 RecallStrategyRegistry**

```java
package com.rec.strategy.registry;

import com.rec.strategy.recall.RecallStrategy;
import org.springframework.stereotype.Component;

import java.util.List;

@Component
public class RecallStrategyRegistry {
    private final List<RecallStrategy> strategies;

    public RecallStrategyRegistry(List<RecallStrategy> strategies) {
        this.strategies = strategies;
    }

    public List<RecallStrategy> getActiveStrategies() {
        return strategies;
    }
}
```

- [ ] **Step 2: 创建其余 3 个 Registry**

```java
package com.rec.strategy.registry;

import com.rec.strategy.ranking.RankingStrategy;
import com.rec.strategy.reranking.RerankingStrategy;
import com.rec.strategy.coldstart.ColdStartStrategy;
import org.springframework.stereotype.Component;

import java.util.List;

@Component
public class RankingStrategyRegistry {
    private final List<RankingStrategy> strategies;

    public RankingStrategyRegistry(List<RankingStrategy> strategies) {
        this.strategies = strategies;
    }

    public List<RankingStrategy> getActiveStrategies() {
        return strategies;
    }
}

@Component
public class RerankingStrategyRegistry {
    private final List<RerankingStrategy> strategies;

    public RerankingStrategyRegistry(List<RerankingStrategy> strategies) {
        this.strategies = strategies;
    }

    public List<RerankingStrategy> getActiveStrategies() {
        return strategies;
    }
}

@Component
public class ColdStartStrategyRegistry {
    private final List<ColdStartStrategy> strategies;

    public ColdStartStrategyRegistry(List<ColdStartStrategy> strategies) {
        this.strategies = strategies;
    }

    public List<ColdStartStrategy> getActiveStrategies() {
        return strategies;
    }
}
```

- [ ] **Step 3: 验证编译并提交**

```bash
mvn compile -pl recommend-strategy && \
git add recommend-strategy/ && \
git commit -m "feat: add strategy registry collectors"
```

---

### Task 13: Pipeline — Context + SnakeMerge

**Files:**
- Create: `recommend-pipeline/src/main/java/com/rec/pipeline/PipelineContext.java`
- Create: `recommend-pipeline/src/main/java/com/rec/pipeline/SnakeMergeUtil.java`

- [ ] **Step 1: 创建 PipelineContext**

```java
package com.rec.pipeline;

import com.rec.common.model.pipeline.*;

import java.util.*;

public record PipelineContext(
    Map<String, Object> userFeatures,
    List<Long> histMovieIds,
    boolean isColdStart,
    List<RecallItem> recallCandidates,
    Map<Long, ItemFeatures> itemFeaturesMap,
    List<RankedItem> rankedItems,
    List<RecommendationItem> rerankedItems
) {
    public static PipelineContext initial(Map<String, Object> userFeatures) {
        return new PipelineContext(
            new HashMap<>(userFeatures), List.of(), false,
            List.of(), Map.of(), List.of(), List.of()
        );
    }

    public PipelineContext withUserFeatures(Map<String, Object> enriched) {
        Map<String, Object> merged = new HashMap<>(this.userFeatures);
        merged.putAll(enriched);
        return new PipelineContext(merged, histMovieIds, isColdStart,
            recallCandidates, itemFeaturesMap, rankedItems, rerankedItems);
    }

    public PipelineContext withHistMovieIds(List<Long> ids) {
        return new PipelineContext(userFeatures, ids, isColdStart,
            recallCandidates, itemFeaturesMap, rankedItems, rerankedItems);
    }

    public PipelineContext withColdStart(boolean coldStart) {
        return new PipelineContext(userFeatures, histMovieIds, coldStart,
            recallCandidates, itemFeaturesMap, rankedItems, rerankedItems);
    }

    public PipelineContext withRecallCandidates(List<RecallItem> candidates) {
        return new PipelineContext(userFeatures, histMovieIds, isColdStart,
            candidates, itemFeaturesMap, rankedItems, rerankedItems);
    }

    public PipelineContext withItemFeatures(Map<Long, ItemFeatures> features) {
        return new PipelineContext(userFeatures, histMovieIds, isColdStart,
            recallCandidates, features, rankedItems, rerankedItems);
    }

    public PipelineContext withRankedItems(List<RankedItem> items) {
        return new PipelineContext(userFeatures, histMovieIds, isColdStart,
            recallCandidates, itemFeaturesMap, items, rerankedItems);
    }

    public PipelineContext withRerankedItems(List<RecommendationItem> items) {
        return new PipelineContext(userFeatures, histMovieIds, isColdStart,
            recallCandidates, itemFeaturesMap, rankedItems, items);
    }
}
```

- [ ] **Step 2: 创建 SnakeMergeUtil**

```java
package com.rec.pipeline;

import com.rec.common.model.pipeline.RecallItem;

import java.util.*;
import java.util.stream.Collectors;

public final class SnakeMergeUtil {

    private SnakeMergeUtil() {}

    public static List<RecallItem> snakeMerge(List<List<RecallItem>> resultsList, int topK) {
        if (resultsList.isEmpty()) return List.of();

        Set<Long> seen = new HashSet<>();
        List<RecallItem> merged = new ArrayList<>();

        int maxLen = resultsList.stream().mapToInt(List::size).max().orElse(0);

        for (int i = 0; i < maxLen; i++) {
            for (int j = 0; j < resultsList.size(); j++) {
                List<RecallItem> list = resultsList.get(j);
                int idx = (j % 2 == 0) ? i : (list.size() - 1 - i);
                if (idx >= 0 && idx < list.size()) {
                    RecallItem item = list.get(idx);
                    if (seen.add(item.movieId())) {
                        merged.add(item);
                        if (merged.size() >= topK) {
                            return merged;
                        }
                    }
                }
            }
        }
        return merged;
    }

    public static List<RecallItem> roundRobinMerge(List<List<RecallItem>> resultsList, int topK) {
        if (resultsList.isEmpty()) return List.of();

        Set<Long> seen = new HashSet<>();
        List<RecallItem> merged = new ArrayList<>();

        int maxLen = resultsList.stream().mapToInt(List::size).max().orElse(0);

        for (int i = 0; i < maxLen; i++) {
            for (List<RecallItem> list : resultsList) {
                if (i < list.size()) {
                    RecallItem item = list.get(i);
                    if (seen.add(item.movieId())) {
                        merged.add(item);
                        if (merged.size() >= topK) {
                            return merged;
                        }
                    }
                }
            }
        }
        return merged;
    }
}
```

- [ ] **Step 3: 验证编译并提交**

```bash
mvn compile -pl recommend-pipeline && \
git add recommend-pipeline/ && \
git commit -m "feat: add PipelineContext and SnakeMergeUtil"
```

---

### Task 14: Pipeline — 6 个 Stage + 主 Pipeline

**Files:**
- Create: `recommend-pipeline/src/main/java/com/rec/pipeline/UserFeatureEnrichmentStage.java`
- Create: `recommend-pipeline/src/main/java/com/rec/pipeline/ColdStartDetectionStage.java`
- Create: `recommend-pipeline/src/main/java/com/rec/pipeline/ColdStartPipeline.java`
- Create: `recommend-pipeline/src/main/java/com/rec/pipeline/RecallStage.java`
- Create: `recommend-pipeline/src/main/java/com/rec/pipeline/RankingStage.java`
- Create: `recommend-pipeline/src/main/java/com/rec/pipeline/RerankingStage.java`
- Create: `recommend-pipeline/src/main/java/com/rec/pipeline/RecommendationPipeline.java`

- [ ] **Step 1: 创建 UserFeatureEnrichmentStage**

```java
package com.rec.pipeline;

import com.rec.repository.mapper.UserMapper;
import com.rec.repository.redis.UserProfileRedisRepository;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;

import java.util.*;

@Component
public class UserFeatureEnrichmentStage {

    private final UserProfileRedisRepository redisRepo;
    private final UserMapper userMapper;

    public UserFeatureEnrichmentStage(UserProfileRedisRepository redisRepo, UserMapper userMapper) {
        this.redisRepo = redisRepo;
        this.userMapper = userMapper;
    }

    public Mono<PipelineContext> execute(PipelineContext ctx) {
        Long userId = (Long) ctx.userFeatures().get("userId");
        if (userId == null) {
            return Mono.just(ctx);
        }

        Mono<Map<String, String>> profileMono = redisRepo.getUserProfile(userId);
        Mono<List<Long>> historyMono = redisRepo.getUserHistory(userId, 100);

        return Mono.zip(profileMono, historyMono)
            .flatMap(tuple -> {
                Map<String, String> profile = tuple.getT1();
                List<Long> history = tuple.getT2();

                Map<String, Object> enriched = new HashMap<>();
                profile.forEach((k, v) -> enriched.put(k, v));
                if (!history.isEmpty()) {
                    enriched.put("histMovieIds", history);
                }

                // Redis 缺失时 DB 兜底
                if (profile.isEmpty()) {
                    var user = userMapper.findActiveById(userId);
                    if (user != null) {
                        if (user.getGender() != null) enriched.put("gender", user.getGender());
                        if (user.getAge() != null) enriched.put("age", user.getAge());
                        if (user.getOccupation() != null) enriched.put("occupation", user.getOccupation());
                        if (user.getZipCode() != null) enriched.put("zipCode", user.getZipCode());
                    }
                }

                PipelineContext enrichedCtx = ctx.withUserFeatures(enriched);
                if (!history.isEmpty()) {
                    enrichedCtx = enrichedCtx.withHistMovieIds(history);
                }
                return Mono.just(enrichedCtx);
            });
    }
}
```

- [ ] **Step 2: 创建 ColdStartDetectionStage**

```java
package com.rec.pipeline;

import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;

@Component
public class ColdStartDetectionStage {

    private static final int COLD_START_THRESHOLD = 5;

    public Mono<PipelineContext> execute(PipelineContext ctx) {
        boolean isColdStart = ctx.histMovieIds().size() < COLD_START_THRESHOLD;
        return Mono.just(ctx.withColdStart(isColdStart));
    }
}
```

- [ ] **Step 3: 创建 ColdStartPipeline**

```java
package com.rec.pipeline;

import com.rec.common.model.pipeline.RecallItem;
import com.rec.strategy.coldstart.ColdStartStrategy;
import com.rec.strategy.registry.ColdStartStrategyRegistry;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

import java.util.List;

@Component
public class ColdStartPipeline {

    private final ColdStartStrategyRegistry registry;

    public ColdStartPipeline(ColdStartStrategyRegistry registry) {
        this.registry = registry;
    }

    public Mono<PipelineContext> execute(PipelineContext ctx, int topK) {
        List<ColdStartStrategy> strategies = registry.getActiveStrategies();

        return Flux.fromIterable(strategies)
            .flatMap(strategy -> strategy.recommend(ctx.userFeatures(), topK)
                .map(items -> new WeightedResult(strategy.getWeight(), items)))
            .collectList()
            .map(results -> weightedRoundRobinMerge(results, topK))
            .map(ctx::withRecallCandidates);
    }

    private List<RecallItem> weightedRoundRobinMerge(List<WeightedResult> results, int topK) {
        List<List<RecallItem>> lists = results.stream()
            .map(WeightedResult::items)
            .toList();
        return SnakeMergeUtil.roundRobinMerge(lists, topK);
    }

    private record WeightedResult(int weight, List<RecallItem> items) {}
}
```

- [ ] **Step 4: 创建 RecallStage**

```java
package com.rec.pipeline;

import com.rec.strategy.recall.RecallStrategy;
import com.rec.strategy.registry.RecallStrategyRegistry;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

@Component
public class RecallStage {

    private final RecallStrategyRegistry registry;

    public RecallStage(RecallStrategyRegistry registry) {
        this.registry = registry;
    }

    public Mono<PipelineContext> execute(PipelineContext ctx, int topK) {
        return Flux.fromIterable(registry.getActiveStrategies())
            .flatMap(strategy ->
                strategy.recall(ctx.userFeatures(), topK)
                    .onErrorResume(e -> Mono.just(List.of()))
            )
            .collectList()
            .map(results -> SnakeMergeUtil.snakeMerge(results, topK))
            .map(ctx::withRecallCandidates);
    }
}
```

- [ ] **Step 5: 创建 RankingStage**

```java
package com.rec.pipeline;

import com.rec.common.model.pipeline.*;
import com.rec.repository.mapper.MovieMapper;
import com.rec.repository.entity.MovieEntity;
import com.rec.strategy.ranking.RankingStrategy;
import com.rec.strategy.registry.RankingStrategyRegistry;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;

import java.util.*;
import java.util.stream.Collectors;

@Component
public class RankingStage {

    private final RankingStrategyRegistry registry;
    private final MovieMapper movieMapper;

    public RankingStage(RankingStage.RankingStrategyRegistry registry, MovieMapper movieMapper) {
        this.registry = registry;
        this.movieMapper = movieMapper;
    }

    public Mono<PipelineContext> execute(PipelineContext ctx, int topK) {
        List<Long> movieIds = ctx.recallCandidates().stream()
            .map(RecallItem::movieId).collect(Collectors.toList());

        Map<Long, ItemFeatures> itemFeaturesMap = fetchItemFeatures(movieIds);

        List<RankingStrategy> strategies = registry.getActiveStrategies();
        RankingStrategy primary = strategies.isEmpty() ? null : strategies.get(0);

        if (primary == null) {
            return Mono.just(ctx.withRankedItems(
                ctx.recallCandidates().stream()
                    .map(c -> new RankedItem(c.movieId(), c.score(), c.score(), c.recallType(),
                        List.of(), 0))
                    .limit(topK)
                    .toList()
            ).withItemFeatures(itemFeaturesMap));
        }

        return primary.rank(ctx.recallCandidates(), ctx.userFeatures(), itemFeaturesMap)
            .onErrorResume(e -> {
                if (strategies.size() > 1) {
                    return strategies.get(1).rank(ctx.recallCandidates(), ctx.userFeatures(), itemFeaturesMap);
                }
                return Mono.just(ctx.recallCandidates().stream()
                    .map(c -> new RankedItem(c.movieId(), c.score(), c.score(), c.recallType(),
                        List.of(), 0))
                    .toList());
            })
            .map(items -> items.stream().limit(topK).toList())
            .map(ctx::withRankedItems)
            .map(c -> c.withItemFeatures(itemFeaturesMap));
    }

    private Map<Long, ItemFeatures> fetchItemFeatures(List<Long> movieIds) {
        Map<Long, ItemFeatures> map = new HashMap<>();
        for (Long id : movieIds) {
            MovieEntity m = movieMapper.selectById(id);
            if (m != null) {
                map.put(id, new ItemFeatures(
                    m.getGenres() != null && m.getGenres().length > 0 ? m.getGenres()[0] : null,
                    m.getGenres() != null ? Arrays.asList(m.getGenres()) : List.of(),
                    m.getIsAdult() != null ? m.getIsAdult() : 0,
                    m.getYear() != null ? m.getYear() : 0
                ));
            }
        }
        return map;
    }
}
```

- [ ] **Step 6: 创建 RerankingStage**

```java
package com.rec.pipeline;

import com.rec.common.model.pipeline.*;
import com.rec.strategy.reranking.RerankingStrategy;
import com.rec.strategy.registry.RerankingStrategyRegistry;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;

import java.util.List;
import java.util.stream.Collectors;

@Component
public class RerankingStage {

    private final RerankingStrategyRegistry registry;

    public RerankingStage(RerankingStrategyRegistry registry) {
        this.registry = registry;
    }

    public Mono<PipelineContext> execute(PipelineContext ctx) {
        List<RankedItem> items = ctx.rankedItems();

        Mono<List<RankedItem>> result = Mono.just(items);
        for (RerankingStrategy strategy : registry.getActiveStrategies()) {
            result = result.flatMap(it ->
                strategy.rerank(it, ctx.userFeatures())
                    .onErrorResume(e -> Mono.just(it))
            );
        }

        return result.map(ranked -> {
            List<RecommendationItem> recs = ranked.stream()
                .map(r -> new RecommendationItem(r.movieId(), r.score(), r.recallType()))
                .collect(Collectors.toList());
            return ctx.withRerankedItems(recs);
        });
    }
}
```

- [ ] **Step 7: 创建主 Pipeline**

```java
package com.rec.pipeline;

import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;

import java.time.Duration;
import java.util.Map;

@Component
public class RecommendationPipeline {

    private static final int RECALL_TOP_K = 100;
    private static final int RANK_TOP_K = 20;
    private static final int COLD_START_TOP_K = 20;

    private final UserFeatureEnrichmentStage enrichment;
    private final ColdStartDetectionStage coldStartDetection;
    private final ColdStartPipeline coldStartPipeline;
    private final RecallStage recallStage;
    private final RankingStage rankingStage;
    private final RerankingStage rerankingStage;

    public RecommendationPipeline(
        UserFeatureEnrichmentStage enrichment,
        ColdStartDetectionStage coldStartDetection,
        ColdStartPipeline coldStartPipeline,
        RecallStage recallStage,
        RankingStage rankingStage,
        RerankingStage rerankingStage
    ) {
        this.enrichment = enrichment;
        this.coldStartDetection = coldStartDetection;
        this.coldStartPipeline = coldStartPipeline;
        this.recallStage = recallStage;
        this.rankingStage = rankingStage;
        this.rerankingStage = rerankingStage;
    }

    public Mono<PipelineContext> recommend(Map<String, Object> userFeatures) {
        return Mono.just(PipelineContext.initial(userFeatures))
            // Stage 0: 补充用户特征
            .flatMap(enrichment::execute)
            // Stage 1: 冷启动检测
            .flatMap(coldStartDetection::execute)
            .flatMap(ctx -> {
                if (ctx.isColdStart()) {
                    // 冷启动快速路径
                    return coldStartPipeline.execute(ctx, COLD_START_TOP_K);
                }
                return Mono.just(ctx)
                    // Stage 2: 召回
                    .flatMap(c -> recallStage.execute(c, RECALL_TOP_K))
                    // Stage 3: 排序
                    .flatMap(c -> rankingStage.execute(c, RANK_TOP_K))
                    // Stage 4: 重排
                    .flatMap(rerankingStage::execute);
            })
            .timeout(Duration.ofMillis(800));
    }
}
```

- [ ] **Step 8: 验证编译**

```bash
mvn compile -pl recommend-pipeline
```

Expected: BUILD SUCCESS

- [ ] **Step 9: 提交**

```bash
git add recommend-pipeline/ && \
git commit -m "feat: add pipeline stages and main orchestrator"
```

---

### Task 15: API — Auth + User Handler

**Files:**
- Create: `recommend-api/src/main/java/com/rec/api/handler/AuthHandler.java`
- Create: `recommend-api/src/main/java/com/rec/api/handler/UserHandler.java`

- [ ] **Step 1: 创建 AuthHandler**

```java
package com.rec.api.handler;

import com.rec.common.model.request.*;
import com.rec.common.model.response.TokenResponse;
import com.rec.repository.mapper.UserMapper;
import com.rec.repository.entity.UserEntity;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.server.ServerRequest;
import org.springframework.web.reactive.function.server.ServerResponse;
import reactor.core.publisher.Mono;

@Component
public class AuthHandler {

    private final UserMapper userMapper;

    public AuthHandler(UserMapper userMapper) {
        this.userMapper = userMapper;
    }

    public Mono<ServerResponse> signup(ServerRequest request) {
        return request.bodyToMono(SignupRequest.class)
            .flatMap(req -> {
                var user = new UserEntity();
                user.setEmail(req.email());
                user.setUsername(req.email().split("@")[0]);
                user.setHashedPassword(hashPassword(req.password()));
                user.setGender(req.gender());
                user.setAge(req.age());
                user.setOccupation(req.occupation());
                user.setZipCode(req.zipCode());
                user.setPreferredGenres(req.preferredGenres() != null
                    ? req.preferredGenres().toArray(String[]::new) : null);
                user.setIsActive(1);
                user.setIsSuperuser(0);
                userMapper.insert(user);
                return ServerResponse.ok().bodyValue(new TokenResponse("jwt-placeholder"));
            });
    }

    public Mono<ServerResponse> login(ServerRequest request) {
        return request.bodyToMono(LoginRequest.class)
            .flatMap(req -> {
                var user = userMapper.findByEmail(req.email());
                if (user == null) {
                    return ServerResponse.badRequest().bodyValue("Invalid credentials");
                }
                return ServerResponse.ok().bodyValue(new TokenResponse("jwt-placeholder"));
            });
    }

    private String hashPassword(String password) {
        return password; // TODO: use BCrypt
    }
}
```

- [ ] **Step 2: 创建 UserHandler**

```java
package com.rec.api.handler;

import com.rec.common.model.request.UserUpdateRequest;
import com.rec.common.model.response.*;
import com.rec.repository.mapper.*;
import com.rec.repository.entity.*;
import com.rec.repository.redis.UserProfileRedisRepository;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.server.ServerRequest;
import org.springframework.web.reactive.function.server.ServerResponse;
import reactor.core.publisher.Mono;

import java.util.*;
import java.util.stream.Collectors;

@Component
public class UserHandler {

    private final UserMapper userMapper;
    private final RatingMapper ratingMapper;
    private final MovieMapper movieMapper;
    private final UserProfileRedisRepository redisRepo;

    public UserHandler(UserMapper userMapper, RatingMapper ratingMapper,
                       MovieMapper movieMapper, UserProfileRedisRepository redisRepo) {
        this.userMapper = userMapper;
        this.ratingMapper = ratingMapper;
        this.movieMapper = movieMapper;
        this.redisRepo = redisRepo;
    }

    public Mono<ServerResponse> getProfile(ServerRequest request) {
        Long userId = extractUserId(request);
        var user = userMapper.findActiveById(userId);
        if (user == null) {
            return ServerResponse.notFound().build();
        }

        List<RatingResponse> recentRatings = ratingMapper.findRecentByUser(userId, 10)
            .stream()
            .map(r -> new RatingResponse(r.getUserId(), r.getMovieId(), r.getRating(), r.getTimestamp()))
            .collect(Collectors.toList());

        var profile = new UserProfileResponse(
            user.getUserId(), user.getEmail(), user.getUsername(),
            user.getGender(), user.getAge(), user.getOccupation(), user.getZipCode(),
            user.getIsSuperuser() == 1, user.getCreatedAt(),
            user.getPreferredGenres() != null ? Arrays.asList(user.getPreferredGenres()) : List.of(),
            List.of(), recentRatings
        );

        return ServerResponse.ok().bodyValue(profile);
    }

    public Mono<ServerResponse> updateProfile(ServerRequest request) {
        Long userId = extractUserId(request);
        return request.bodyToMono(UserUpdateRequest.class)
            .flatMap(req -> {
                var user = userMapper.findActiveById(userId);
                if (user == null) {
                    return ServerResponse.notFound().build();
                }
                if (req.gender() != null) user.setGender(req.gender());
                if (req.age() != null) user.setAge(req.age());
                if (req.occupation() != null) user.setOccupation(req.occupation());
                if (req.zipCode() != null) user.setZipCode(req.zipCode());
                if (req.preferredGenres() != null) {
                    user.setPreferredGenres(req.preferredGenres().toArray(String[]::new));
                }
                userMapper.updateById(user);
                return ServerResponse.ok().build();
            });
    }

    private Long extractUserId(ServerRequest request) {
        return Long.parseLong(request.pathVariable("userId"));
    }
}
```

- [ ] **Step 3: 验证编译并提交**

```bash
mvn compile -pl recommend-api && \
git add recommend-api/ && \
git commit -m "feat: add Auth and User handlers"
```

---

### Task 16: API — Movie + Rating Handler

**Files:**
- Create: `recommend-api/src/main/java/com/rec/api/handler/MovieHandler.java`
- Create: `recommend-api/src/main/java/com/rec/api/handler/RatingHandler.java`

- [ ] **Step 1: 创建 MovieHandler**

```java
package com.rec.api.handler;

import com.rec.common.model.request.MovieCreateRequest;
import com.rec.common.model.response.*;
import com.rec.repository.mapper.*;
import com.rec.repository.entity.*;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.server.*;
import reactor.core.publisher.Mono;

import java.util.*;
import java.util.stream.Collectors;

@Component
public class MovieHandler {

    private final MovieMapper movieMapper;
    private final TitlePrincipalMapper titlePrincipalMapper;
    private final NameBasicsMapper nameBasicsMapper;
    private final TitleCrewMapper titleCrewMapper;

    public MovieHandler(MovieMapper movieMapper, TitlePrincipalMapper titlePrincipalMapper,
                        NameBasicsMapper nameBasicsMapper, TitleCrewMapper titleCrewMapper) {
        this.movieMapper = movieMapper;
        this.titlePrincipalMapper = titlePrincipalMapper;
        this.nameBasicsMapper = nameBasicsMapper;
        this.titleCrewMapper = titleCrewMapper;
    }

    public Mono<ServerResponse> create(ServerRequest request) {
        return request.bodyToMono(MovieCreateRequest.class)
            .flatMap(req -> {
                var movie = new MovieEntity();
                movie.setTitle(req.title());
                movie.setImdbId(req.imdbId());
                movie.setYear(req.year());
                movie.setGenres(req.genres() != null ? req.genres().toArray(String[]::new) : null);
                movie.setDescription(req.description());
                movie.setRuntimeMinutes(req.runtimeMinutes());
                movie.setTitleType(req.titleType());
                movie.setImdbRating(req.imdbRating());
                movie.setImdbVotes(req.imdbVotes());
                movieMapper.insert(movie);
                return ServerResponse.ok().build();
            });
    }

    public Mono<ServerResponse> list(ServerRequest request) {
        int page = Integer.parseInt(request.queryParam("page").orElse("1"));
        int size = Integer.parseInt(request.queryParam("page_size").orElse("20"));
        var movies = movieMapper.selectList(null);
        var items = movies.stream()
            .map(m -> new MovieListItem(m.getMovieId(), m.getTitle(), m.getYear(),
                m.getGenres() != null ? Arrays.asList(m.getGenres()) : List.of(),
                m.getAvgRating(), m.getImdbRating()))
            .collect(Collectors.toList());
        var resp = new MovieListResponse(items, movies.size(), page, size, false);
        return ServerResponse.ok().bodyValue(resp);
    }

    public Mono<ServerResponse> popular(ServerRequest request) {
        var movies = movieMapper.findPopular(20);
        var items = movies.stream()
            .map(m -> new MovieListItem(m.getMovieId(), m.getTitle(), m.getYear(),
                m.getGenres() != null ? Arrays.asList(m.getGenres()) : List.of(),
                m.getAvgRating(), m.getImdbRating()))
            .collect(Collectors.toList());
        return ServerResponse.ok().bodyValue(items);
    }

    public Mono<ServerResponse> detail(ServerRequest request) {
        Long id = Long.parseLong(request.pathVariable("id"));
        var m = movieMapper.selectById(id);
        if (m == null) return ServerResponse.notFound().build();
        var detail = new MovieDetailResponse(m.getMovieId(), m.getImdbId(), m.getTitle(),
            m.getYear(), m.getGenres() != null ? Arrays.asList(m.getGenres()) : List.of(),
            m.getDescription(), m.getAvgRating(), m.getRatingCount(),
            m.getImdbRating(), m.getImdbVotes(), m.getRuntimeMinutes(), m.getTitleType());
        return ServerResponse.ok().bodyValue(detail);
    }

    public Mono<ServerResponse> cast(ServerRequest request) {
        Long id = Long.parseLong(request.pathVariable("id"));
        var movie = movieMapper.selectById(id);
        if (movie == null || movie.getImdbId() == null) return ServerResponse.notFound().build();
        var principals = titlePrincipalMapper.findByTconst(movie.getImdbId());
        var cast = principals.stream()
            .filter(p -> "actor".equals(p.getCategory()) || "actress".equals(p.getCategory()))
            .map(p -> new CastMemberResponse(p.getNconst(),
                nameBasicsMapper.findByNconst(p.getNconst()) != null
                    ? nameBasicsMapper.findByNconst(p.getNconst()).getPrimaryName() : "",
                p.getCharacters(), p.getCategory(), p.getOrdering()))
            .collect(Collectors.toList());
        return ServerResponse.ok().bodyValue(
            new MovieCastResponse(id, movie.getTitle(), cast));
    }

    public Mono<ServerResponse> crew(ServerRequest request) {
        Long id = Long.parseLong(request.pathVariable("id"));
        var movie = movieMapper.selectById(id);
        if (movie == null || movie.getImdbId() == null) return ServerResponse.notFound().build();
        var crew = titleCrewMapper.findByTconst(movie.getImdbId());
        return ServerResponse.ok().bodyValue(Map.of(
            "movie_id", id, "movie_title", movie.getTitle(),
            "directors", crew != null ? crew.getDirectors() : new String[]{},
            "writers", crew != null ? crew.getWriters() : new String[]{}
        ));
    }
}
```

- [ ] **Step 2: 创建 RatingHandler (含反馈闭环)**

```java
package com.rec.api.handler;

import com.rec.common.model.request.RatingCreateRequest;
import com.rec.common.model.response.*;
import com.rec.repository.mapper.*;
import com.rec.repository.entity.*;
import com.rec.repository.redis.UserProfileRedisRepository;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.server.*;
import reactor.core.publisher.Mono;

import java.util.*;

@Component
public class RatingHandler {

    private final RatingMapper ratingMapper;
    private final MovieMapper movieMapper;
    private final UserMapper userMapper;
    private final UserProfileRedisRepository redisRepo;

    public RatingHandler(RatingMapper ratingMapper, MovieMapper movieMapper,
                         UserMapper userMapper, UserProfileRedisRepository redisRepo) {
        this.ratingMapper = ratingMapper;
        this.movieMapper = movieMapper;
        this.userMapper = userMapper;
        this.redisRepo = redisRepo;
    }

    public Mono<ServerResponse> createRating(ServerRequest request) {
        Long userId = extractUserId(request);
        return request.bodyToMono(RatingCreateRequest.class)
            .flatMap(req -> {
                var rating = new RatingEntity();
                rating.setUserId(userId);
                rating.setMovieId(req.movieId());
                rating.setRating(req.rating());
                rating.setTimestamp(System.currentTimeMillis());
                ratingMapper.insert(rating);                                 // 1. PG

                updateMovieAvgRating(req.movieId());                         // 1. PG

                return redisRepo.pushUserHistory(userId, req.movieId())      // 3. Redis history
                    .then(redisRepo.updateUserProfile(userId,               // 4. Redis profile
                        Map.of("last_updated", String.valueOf(System.currentTimeMillis()))))
                    .then(redisRepo.updateUCBStats(userId,                  // 5. Redis UCB
                        getMovieGenre(req.movieId()), req.rating()))
                    .then(ServerResponse.ok().bodyValue(
                        new RatingResponse(userId, req.movieId(), req.rating(), rating.getTimestamp())));
            });
    }

    public Mono<ServerResponse> getMovieRating(ServerRequest request) {
        Long userId = extractUserId(request);
        Long movieId = Long.parseLong(request.pathVariable("id"));
        var rating = ratingMapper.findByUserAndMovie(userId, movieId);
        var resp = rating != null
            ? new UserRatingResponse(rating.getRating(), true)
            : new UserRatingResponse(null, false);
        return ServerResponse.ok().bodyValue(resp);
    }

    public Mono<ServerResponse> deleteRating(ServerRequest request) {
        Long userId = extractUserId(request);
        Long movieId = Long.parseLong(request.pathVariable("id"));
        ratingMapper.deleteByUserAndMovie(userId, movieId);
        return ServerResponse.noContent().build();
    }

    private void updateMovieAvgRating(Long movieId) {
        var movie = movieMapper.selectById(movieId);
        if (movie != null) {
            movie.setRatingCount((movie.getRatingCount() != null ? movie.getRatingCount() : 0) + 1);
            movieMapper.updateById(movie);
        }
    }

    private String getMovieGenre(Long movieId) {
        var movie = movieMapper.selectById(movieId);
        if (movie != null && movie.getGenres() != null && movie.getGenres().length > 0) {
            return movie.getGenres()[0];
        }
        return "Unknown";
    }

    private Long extractUserId(ServerRequest request) {
        return Long.parseLong(request.pathVariable("userId"));
    }
}
```

- [ ] **Step 3: 验证编译并提交**

```bash
mvn compile -pl recommend-api && \
git add recommend-api/ && \
git commit -m "feat: add Movie and Rating handlers with feedback loop"
```

---

### Task 17: API — Recommendation + Search + 其他 Handler

**Files:**
- Create: `recommend-api/src/main/java/com/rec/api/handler/RecommendationHandler.java`
- Create: `recommend-api/src/main/java/com/rec/api/handler/SearchHandler.java`
- Create: `recommend-api/src/main/java/com/rec/api/handler/GenreHandler.java`
- Create: `recommend-api/src/main/java/com/rec/api/handler/PeopleHandler.java`
- Create: `recommend-api/src/main/java/com/rec/api/handler/StatsHandler.java`
- Create: `recommend-api/src/main/java/com/rec/api/handler/HealthHandler.java`

- [ ] **Step 1: 创建 RecommendationHandler**

```java
package com.rec.api.handler;

import com.rec.common.model.request.UserFeaturesRequest;
import com.rec.common.model.response.*;
import com.rec.common.model.pipeline.RankedItem;
import com.rec.pipeline.RecommendationPipeline;
import com.rec.repository.mapper.MovieMapper;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.server.*;
import reactor.core.publisher.Mono;

import java.util.*;
import java.util.stream.Collectors;

@Component
public class RecommendationHandler {

    private final RecommendationPipeline pipeline;
    private final MovieMapper movieMapper;

    public RecommendationHandler(RecommendationPipeline pipeline, MovieMapper movieMapper) {
        this.pipeline = pipeline;
        this.movieMapper = movieMapper;
    }

    public Mono<ServerResponse> recommend(ServerRequest request) {
        return request.bodyToMono(UserFeaturesRequest.class)
            .flatMap(req -> {
                Map<String, Object> features = new HashMap<>();
                if (req.userId() != null) features.put("userId", req.userId());
                if (req.gender() != null) features.put("gender", req.gender());
                if (req.age() != null) features.put("age", req.age());
                if (req.occupation() != null) features.put("occupation", req.occupation());
                if (req.zipCode() != null) features.put("zipCode", req.zipCode());
                if (req.histMovieIds() != null) features.put("histMovieIds", req.histMovieIds());
                if (req.preferredGenres() != null) features.put("preferredGenres", req.preferredGenres());

                return pipeline.recommend(features);
            })
            .flatMap(ctx -> {
                var items = ctx.rerankedItems().stream()
                    .map(item -> {
                        var movie = movieMapper.selectById(item.movieId());
                        return new RecommendationItemResponse(
                            item.movieId(),
                            movie != null ? movie.getTitle() : "",
                            movie != null && movie.getGenres() != null
                                ? Arrays.asList(movie.getGenres()) : List.of(),
                            item.score(), null, item.recallType(), null
                        );
                    })
                    .collect(Collectors.toList());

                var resp = new RecommendationResponse(items, items.size(), "deepfm");
                return ServerResponse.ok().bodyValue(resp);
            });
    }

    public Mono<ServerResponse> health(ServerRequest request) {
        return ServerResponse.ok().bodyValue(Map.of("status", "healthy"));
    }
}
```

- [ ] **Step 2: 创建 SearchHandler**

```java
package com.rec.api.handler;

import com.rec.repository.es.MovieSearchRepository;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.server.*;
import reactor.core.publisher.Mono;

import java.util.Map;

@Component
public class SearchHandler {

    private final MovieSearchRepository esRepo;

    public SearchHandler(MovieSearchRepository esRepo) {
        this.esRepo = esRepo;
    }

    public Mono<ServerResponse> searchMovies(ServerRequest request) {
        String q = request.queryParam("q").orElse("");
        int from = Integer.parseInt(request.queryParam("from").orElse("0"));
        int size = Integer.parseInt(request.queryParam("size").orElse("20"));
        return esRepo.searchByKeyword(q, from, size)
            .collectList()
            .flatMap(results -> ServerResponse.ok().bodyValue(results));
    }

    public Mono<ServerResponse> suggest(ServerRequest request) {
        String q = request.queryParam("q").orElse("");
        return esRepo.suggest(q, 10)
            .collectList()
            .flatMap(results -> ServerResponse.ok().bodyValue(results));
    }
}
```

- [ ] **Step 3: 创建 Genre + People + Stats + Health Handler**

```java
package com.rec.api.handler;

import com.rec.common.model.response.*;
import com.rec.repository.mapper.*;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.server.*;
import reactor.core.publisher.Mono;

import java.util.*;

@Component
public class GenreHandler {

    private final GenreMapper genreMapper;

    public GenreHandler(GenreMapper genreMapper) {
        this.genreMapper = genreMapper;
    }

    public Mono<ServerResponse> list(ServerRequest request) {
        return Mono.just(new GenreListResponse(genreMapper.findAllNames()))
            .flatMap(r -> ServerResponse.ok().bodyValue(r));
    }
}

@Component
public class PeopleHandler {

    private final NameBasicsMapper nameBasicsMapper;

    public PeopleHandler(NameBasicsMapper nameBasicsMapper) {
        this.nameBasicsMapper = nameBasicsMapper;
    }

    public Mono<ServerResponse> detail(ServerRequest request) {
        String id = request.pathVariable("id");
        var p = nameBasicsMapper.findByNconst(id);
        if (p == null) return ServerResponse.notFound().build();
        var resp = new PersonDetailResponse(p.getNconst(), p.getPrimaryName(),
            p.getBirthYear(), p.getDeathYear(),
            p.getPrimaryProfession() != null ? Arrays.asList(p.getPrimaryProfession()) : List.of(),
            p.getKnownForTitles() != null ? Arrays.asList(p.getKnownForTitles()) : List.of());
        return ServerResponse.ok().bodyValue(resp);
    }
}

@Component
public class StatsHandler {

    private final MovieMapper movieMapper;
    private final UserMapper userMapper;
    private final RatingMapper ratingMapper;

    public StatsHandler(MovieMapper movieMapper, UserMapper userMapper, RatingMapper ratingMapper) {
        this.movieMapper = movieMapper;
        this.userMapper = userMapper;
        this.ratingMapper = ratingMapper;
    }

    public Mono<ServerResponse> dashboard(ServerRequest request) {
        var stats = Map.of(
            "total_movies", (Object) movieMapper.selectCount(null),
            "total_users", userMapper.selectCount(null),
            "total_ratings", ratingMapper.selectCount(null)
        );
        return ServerResponse.ok().bodyValue(stats);
    }
}

@Component
public class HealthHandler {

    public HealthHandler() {}

    public Mono<ServerResponse> check(ServerRequest request) {
        return ServerResponse.ok().bodyValue(Map.of(
            "status", "healthy", "version", "1.0.0"
        ));
    }
}
```

- [ ] **Step 4: 验证编译并提交**

```bash
mvn compile -pl recommend-api && \
git add recommend-api/ && \
git commit -m "feat: add Recommendation, Search, Genre, People, Stats and Health handlers"
```

---

### Task 18: API — Router + Global Error Handler + Application

**Files:**
- Create: `recommend-api/src/main/java/com/rec/api/router/ApiRouter.java`
- Create: `recommend-api/src/main/java/com/rec/api/error/GlobalErrorWebExceptionHandler.java`
- Create: `recommend-api/src/main/java/com/rec/api/RecommendApplication.java`

- [ ] **Step 1: 创建 ApiRouter**

```java
package com.rec.api.router;

import com.rec.api.handler.*;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.reactive.function.server.*;

import static org.springframework.web.reactive.function.server.RequestPredicates.*;

@Configuration
public class ApiRouter {

    @Bean
    public RouterFunction<ServerResponse> routes(
        AuthHandler authHandler, UserHandler userHandler, MovieHandler movieHandler,
        RatingHandler ratingHandler, RecommendationHandler recommendationHandler,
        SearchHandler searchHandler, GenreHandler genreHandler,
        PeopleHandler peopleHandler, StatsHandler statsHandler, HealthHandler healthHandler
    ) {
        return RouterFunctions
            // 健康检查
            .route(GET("/health"), healthHandler::check)
            // Auth
            .andRoute(POST("/api/auth/signup"), authHandler::signup)
            .andRoute(POST("/api/auth/login"), authHandler::login)
            // Users
            .andRoute(GET("/api/users/me"), userHandler::getProfile)
            .andRoute(PUT("/api/users/me"), userHandler::updateProfile)
            // Movies
            .andRoute(POST("/api/movies"), movieHandler::create)
            .andRoute(GET("/api/movies"), movieHandler::list)
            .andRoute(GET("/api/movies/popular"), movieHandler::popular)
            .andRoute(GET("/api/movies/{id}"), movieHandler::detail)
            .andRoute(GET("/api/movies/{id}/cast"), movieHandler::cast)
            .andRoute(GET("/api/movies/{id}/crew"), movieHandler::crew)
            // Ratings
            .andRoute(POST("/api/ratings"), ratingHandler::createRating)
            .andRoute(GET("/api/ratings/movie/{id}"), ratingHandler::getMovieRating)
            .andRoute(DELETE("/api/ratings/movie/{id}"), ratingHandler::deleteRating)
            // Recommendations
            .andRoute(POST("/api/recommendations/recommend"), recommendationHandler::recommend)
            .andRoute(GET("/api/recommendations/health"), recommendationHandler::health)
            // Search
            .andRoute(GET("/api/search/movies"), searchHandler::searchMovies)
            .andRoute(GET("/api/search/suggest"), searchHandler::suggest)
            // Genres
            .andRoute(GET("/api/genres"), genreHandler::list)
            // People
            .andRoute(GET("/api/people/{id}"), peopleHandler::detail)
            // Stats
            .andRoute(GET("/api/stats"), statsHandler::dashboard);
    }
}
```

- [ ] **Step 2: 创建 GlobalErrorWebExceptionHandler**

```java
package com.rec.api.error;

import com.rec.common.exception.*;
import org.springframework.boot.autoconfigure.web.WebProperties;
import org.springframework.boot.autoconfigure.web.reactive.error.AbstractErrorWebExceptionHandler;
import org.springframework.boot.web.reactive.error.ErrorAttributes;
import org.springframework.context.ApplicationContext;
import org.springframework.core.annotation.Order;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.codec.ServerCodecConfigurer;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.BodyInserters;
import org.springframework.web.reactive.function.server.*;
import reactor.core.publisher.Mono;

import java.util.Map;
import java.util.UUID;

@Component
@Order(-2)
public class GlobalErrorWebExceptionHandler extends AbstractErrorWebExceptionHandler {

    public GlobalErrorWebExceptionHandler(ErrorAttributes errorAttributes,
                                           WebProperties webProperties,
                                           ApplicationContext context,
                                           ServerCodecConfigurer codecConfigurer) {
        super(errorAttributes, webProperties.getResources(), context);
        setMessageWriters(codecConfigurer.getWriters());
    }

    @Override
    protected RouterFunction<ServerResponse> getRoutingFunction(ErrorAttributes errorAttributes) {
        return RouterFunctions.route(RequestPredicates.all(), this::renderErrorResponse);
    }

    private Mono<ServerResponse> renderErrorResponse(ServerRequest request) {
        Throwable error = getError(request);
        HttpStatus status;
        String code;

        if (error instanceof InferenceException) {
            status = HttpStatus.SERVICE_UNAVAILABLE;
            code = "INFERENCE_ERROR";
        } else if (error instanceof RecommendationException) {
            status = HttpStatus.INTERNAL_SERVER_ERROR;
            code = "RECOMMEND_ERROR";
        } else if (error instanceof AuthException) {
            status = HttpStatus.UNAUTHORIZED;
            code = "AUTH_ERROR";
        } else if (error instanceof DataAccessException) {
            status = HttpStatus.INTERNAL_SERVER_ERROR;
            code = "DATA_ERROR";
        } else {
            status = HttpStatus.INTERNAL_SERVER_ERROR;
            code = "INTERNAL_ERROR";
        }

        var body = Map.of(
            "code", code,
            "message", error.getMessage() != null ? error.getMessage() : "Unexpected error",
            "traceId", UUID.randomUUID().toString()
        );

        return ServerResponse.status(status)
            .contentType(MediaType.APPLICATION_JSON)
            .body(BodyInserters.fromValue(body));
    }
}
```

- [ ] **Step 3: 创建 RecommendApplication**

```java
package com.rec.api;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;

@SpringBootApplication(scanBasePackages = "com.rec")
@ConfigurationPropertiesScan(basePackages = "com.rec")
public class RecommendApplication {

    public static void main(String[] args) {
        SpringApplication.run(RecommendApplication.class, args);
    }
}
```

- [ ] **Step 4: 创建 application.yml**

```java
// 放在 recommend-api/src/main/resources/application.yml
```

- [ ] **Step 5: 验证编译并提交**

```bash
mvn compile -pl recommend-api && \
git add recommend-api/ && \
git commit -m "feat: add API router, global error handler, and application entry point"
```

---

### Task 19: 配置文件

**Files:**
- Create: `recommend-api/src/main/resources/application.yml`

- [ ] **Step 1: 创建 application.yml**

```yaml
server:
  port: 8080

spring:
  application:
    name: rec-recommend-service
  threads:
    virtual:
      enabled: true

  datasource:
    url: jdbc:postgresql://localhost:5432/rec_db
    username: rec
    password: rec123
    driver-class-name: org.postgresql.Driver
    hikari:
      maximum-pool-size: 20
      minimum-idle: 5
      connection-timeout: 3000
      idle-timeout: 600000
      max-lifetime: 1800000

  data:
    redis:
      host: localhost
      port: 6379
      database: 0
      lettuce:
        pool:
          max-active: 16
          max-idle: 8
          min-idle: 4

    elasticsearch:
      client:
        reactive:
          endpoints: localhost:9200

mybatis-plus:
  configuration:
    map-underscore-to-camel-case: true
    log-impl: org.apache.ibatis.logging.slf4j.Slf4jImpl
  global-config:
    db-config:
      id-type: auto

recommend:
  rpc:
    client: http
    inference:
      base-url: http://python-inference:8080
      connect-timeout: 500
      read-timeout: 2000
      max-retries: 1

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

management:
  endpoints:
    web:
      exposure:
        include: health,metrics
```

- [ ] **Step 2: 验证并提交**

```bash
git add recommend-api/src/main/resources/application.yml && \
git commit -m "feat: add application configuration"
```

---

### Task 20: 整体编译验证 + 提交

- [ ] **Step 1: 全量编译**

```bash
mvn clean compile -DskipTests
```

Expected: BUILD SUCCESS (所有模块编译通过)

- [ ] **Step 2: 如果有编译错误，按 mvn 输出逐文件修复**

- [ ] **Step 3: 编译成功后提交**

```bash
git add -A && \
git commit -m "fix: resolve compilation issues across all modules"
```
