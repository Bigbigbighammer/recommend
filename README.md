# Rec — 电影推荐系统

基于 MovieLens 1M + IMDb 数据集的电影推荐系统，结合 Docker Compose 部署。

## 架构

```
nginx (Vue 3)  →  Java API (Spring WebFlux)
                      ├── PostgreSQL 16
                      ├── Redis 7
                      ├── Elasticsearch 8
                      └── Python Inference
                          └── DeepFM + YouTubeDNN 模型
```

> 端口映射以 `docker-compose.yml` 中 `ports` 配置为准。

## 前置要求

- Docker 20+ (with docker compose plugin)
- JDK 17+
- Maven 3.8+
- Python 3.12+ (for data ingestion)
- 可用磁盘空间 ≥ 10GB

## 1. 启动基础设施

```bash
# 启动 PostgreSQL, Redis, Elasticsearch, Python 推理服务
docker compose up -d postgres redis elasticsearch python-inference

# 等待健康检查通过（约 30 秒）
docker compose ps
```

## 2. 下载并导入数据

```bash
# 下载数据集（约 300MB 压缩包，解压后 ~2GB）
wget https://funrec-datasets.s3.eu-west-3.amazonaws.com/funrec-movielens-1m.zip
unzip funrec-movielens-1m.zip -d scripts/data/

# 安装 Python 依赖
pip install pandas psycopg2-binary redis

# 导入数据（PostgreSQL + Elasticsearch + Redis + posters）
python scripts/ingest_data.py --create-test-user

# 导入内容：
#  - PostgreSQL: movies, users, ratings, title_ratings, name_basics,
#                title_crew, title_principals, title_akas, genres
#  - Elasticsearch: 3883 电影文档 (搜索索引)
#  - Redis: 6041 用户画像 + 100万 条评分历史
#  - posters: 3883 张海报 (data/posters/)
```

## 3. 生成嵌入向量

```bash
python scripts/generate_embeddings.py
# 输出: data/item_emb.npy (3883 × 16)
#       data/movie_ids.npy (3883 IDs)
```

## 4. 构建并启动全部服务

```bash
# 构建前端镜像 + Java 镜像，启动全部 6 个服务
docker compose up -d --build

# 确认所有服务运行正常
docker compose ps
```

## 5. 访问

端口以 `docker-compose.yml` 中 `ports` 映射为准（宿主机端口:容器端口）。

| 入口 | 默认地址 |
|------|------|
| 前端 (Vue 3) | http://localhost:8088 |
| Java API | http://localhost:8082 |
| Python API | http://localhost:8081 |
| Elasticsearch | http://localhost:9200 |

### 测试用户

```
邮箱: test@rec.dev
密码: test123456
```

## 常用命令

```bash
# 查看日志
docker compose logs -f java
docker compose logs -f python-inference

# 重启 Java 服务 (代码修改后)
docker compose restart java

# 重新构建并重启某个服务
docker compose up -d --build nginx

# 运行浏览器 E2E 测试
cd frontend && npx playwright test

# 清空所有数据重建
docker compose down -v
python scripts/ingest_data.py --create-test-user
python scripts/generate_embeddings.py
docker compose up -d --build
```

## 项目结构

```
recommend/
├── docker-compose.yml       # 6 容器编排
├── Dockerfile.java          # Java API 镜像
├── Dockerfile.python        # Python 推理镜像
├── Dockerfile.frontend      # Vue 前端镜像
├── nginx.conf               # Nginx 反向代理
├── docker/init-db/          # PG 初始化 SQL
├── scripts/
│   ├── ingest_data.py       # 数据导入脚本
│   ├── generate_embeddings.py
│   └── example/             # 参考脚本
├── recommend-api/           # Spring WebFlux API
├── recommend-common/        # 共享 DTO / model
├── recommend-pipeline/      # 推荐流水线
├── recommend-repository/    # MyBatis-Plus + ES
├── recommend-rpc/           # Python RPC 客户端
├── recommend-strategy/      # 召回 + 排序策略
├── python-service/          # PyTorch 推理服务
└── frontend/                # Vue 3 前端
```
