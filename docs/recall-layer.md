# 召回层实现与复现说明

本文档说明本次召回层完成的内容、离线评测方式、线上接入方式，以及当前推荐结果中和排序层/前端展示相关的注意事项。

## 1. 完成内容

本次主要完成推荐系统的召回层，实现了离线实验和在线接入两部分。

### 1.1 离线召回算法

新增离线评测脚本：

```text
scripts/offline_recall_eval.py
```

当前支持的召回算法包括：

| 方法 | 说明 |
|---|---|
| Popular | 全局热门电影召回 |
| ItemCF | 基于物品共现的协同过滤召回 |
| SeqCF | 基于用户观看/评分序列的转移召回 |
| EASE | 线性协同过滤召回，MovieLens 上表现较强 |
| Swing | 带用户活跃度惩罚的共现召回 |
| UserCF | 基于相似用户的协同过滤召回 |
| Content | 基于类型、年份、评分、IMDb 信息的内容向量召回 |
| Genre | 基于用户偏好类型的召回 |
| Hybrid Recall | 多路召回结果加权 RRF 融合 |

评测指标包括：

```text
Recall
Precision
NDCG
HitRate
Coverage
```

### 1.2 在线召回策略

新增或接入的 Java 在线召回策略包括：

```text
recommend-strategy/src/main/java/com/rec/strategy/recall/ItemCFRecallStrategy.java
recommend-strategy/src/main/java/com/rec/strategy/recall/SeqCFRecallStrategy.java
recommend-strategy/src/main/java/com/rec/strategy/recall/EASERecallStrategy.java
recommend-strategy/src/main/java/com/rec/strategy/recall/SwingRecallStrategy.java
recommend-strategy/src/main/java/com/rec/strategy/recall/UserCFRecallStrategy.java
recommend-strategy/src/main/java/com/rec/strategy/recall/PopularRecallStrategy.java
recommend-strategy/src/main/java/com/rec/strategy/recall/UserPreferenceRecallStrategy.java
recommend-strategy/src/main/java/com/rec/strategy/recall/YouTubeDNNRecallStrategy.java
```

线上融合方式在以下文件中实现：

```text
recommend-pipeline/src/main/java/com/rec/pipeline/RecallStage.java
recommend-pipeline/src/main/java/com/rec/pipeline/SnakeMergeUtil.java
```

当前线上召回融合采用加权 RRF，默认权重在：

```text
recommend-api/src/main/resources/application.yml
```

默认配置：

```yaml
recommend:
  recall-fusion:
    weights: itemcf=2.0,usercf=1.8,ease=1.25,seqcf=1.1,bpr=0.0,swing=0.7,user_preference=0.5,item_embedding=0.3,youtubednn=0.4,popular=0.05
    rrf-k: 60
```

其中 BPR 当前默认关闭，原因是本地训练时间较长，作为后续可选优化保留。

## 2. 离线实验结果

数据集：MovieLens 1M / FunRec MovieLens 1M

正样本口径：

```text
rating >= 8.0
```

切分方式：

```text
按用户时间序列切分，每个用户最后一部分正样本作为测试集，前面的正样本作为训练历史。
```

当前最新同口径结果：

| 方法 | Recall@100 | Precision@100 | NDCG@100 | HitRate@100 | Coverage@100 |
|---|---:|---:|---:|---:|---:|
| 原混合召回 | 0.4015 | 0.0591 | 0.2205 | 0.9438 | 1609 |
| 加 SeqCF 后 | 0.4233 | 0.0614 | 0.2349 | 0.9559 | 1883 |
| 单独 EASE | 0.4231 | 0.0606 | 0.2379 | 0.9599 | 1473 |
| 加 EASE 后 Hybrid Recall | 0.4286 | 0.0620 | 0.2388 | 0.9586 | 1733 |
| 加 PyTorch YouTubeDNN 后 Hybrid Recall | 0.4687 | 0.0660 | 0.2725 | 0.9645 | 2243 |

最终主要提升来自：

```text
PyTorch YouTubeDNN + EASE + SeqCF + ItemCF + UserCF 的多路召回融合
```

YouTubeDNN 已升级为 PyTorch 双塔版本。16 epoch 离线模型的单路 Recall@100 达到 0.4344，加入混合召回后最佳 Recall@100 达到 0.4687。

## 3. 如何复现实验

假设数据集位于：

```powershell
D:\BDhomework\recommend-master\scripts\data\funrec-movielens-1m
```

进入项目目录：

```powershell
cd D:\BDhomework\recommend-latest
```

运行离线召回评测：

```powershell
python scripts\offline_recall_eval.py --data-dir "D:\BDhomework\recommend-master\scripts\data\funrec-movielens-1m" --output test-results\recall_eval_ease_full.csv
```

评测结果会输出到：

```text
test-results/recall_eval_ease_full.csv
```

## 4. 如何生成线上召回产物

线上 Java 服务需要读取离线生成的召回文件。

运行：

```powershell
python scripts\build_recall_artifacts.py --data-dir "D:\BDhomework\recommend-master\scripts\data\funrec-movielens-1m" --out-dir data
```

会生成：

```text
data/itemcf_sim.csv
data/seqcf_sim.csv
data/ease_sim.csv
data/swing_sim.csv
data/usercf_sim.csv
data/user_positive_items.csv
data/popular_movies.csv
```

注意：

```text
data/ 是运行时产物目录，不建议提交到 GitHub。
```

队友拉取代码后，按上面的命令重新生成即可。

## 5. YouTubeDNN 训练与接入

旧版轻量 YouTubeDNN 训练脚本：

```text
scripts/train_youtubednn.py
```

训练命令：

```powershell
python scripts\train_youtubednn.py --data-dir "D:\BDhomework\recommend-master\scripts\data\funrec-movielens-1m" --out-dir data --epochs 2 --dim 32 --max-samples 500000 --eval-output test-results\youtubednn_eval.csv
```

输出：

```text
data/item_emb.npy
data/movie_ids.npy
data/youtube_user_item_emb.npy
data/youtubednn_meta.json
```

新版完整 PyTorch YouTubeDNN 训练脚本：

```text
scripts/train_youtubednn_torch.py
```

离线评测与最终线上模型训练命令：

```powershell
python scripts\train_youtubednn_torch.py --data-dir "D:\BDhomework\recommend-master\scripts\data\funrec-movielens-1m" --epochs 16 --dim 64 --hidden-dim 128 --max-samples 500000 --batch-size 512 --eval-output test-results\youtubednn_torch_online_e16_eval.csv --out-dir data\youtubednn_torch_online_e16
```

该命令会先用时间切分做离线评测，然后用全部正样本训练最终线上模型。

最终线上产物需要放在 `data/` 根目录：

```text
data/youtube_dnn_torch.pt
data/item_emb.npy
data/movie_ids.npy
data/youtubednn_torch_meta.json
```

当前 Python 推理服务会优先加载：

```text
data/youtube_dnn_torch.pt
```

如果该文件存在，`/api/predict/recall` 会使用 PyTorch user tower 生成用户向量；如果不存在，才回退到旧的 NumPy pooling 版本。

Java 的 `YouTubeDNNRecallStrategy` 仍然调用 Python `/api/predict/recall` 获取 user vector，再用 `ItemEmbeddingStore` 读取 `data/item_emb.npy` 做 topK 向量召回。

PyTorch YouTubeDNN 混合召回测试脚本：

```text
scripts/eval_hybrid_youtubednn_torch.py
```

最佳离线融合结果：

| 方法 | Recall@100 | Precision@100 | NDCG@100 |
|---|---:|---:|---:|
| 不加 PyTorch YouTubeDNN 的混合召回 | 0.4312 | 0.0624 | 0.2410 |
| 单独 PyTorch YouTubeDNN | 0.4344 | 0.0605 | 0.2396 |
| 加入 PyTorch YouTubeDNN 的混合召回 | 0.4687 | 0.0660 | 0.2725 |

## 6. 如何启动并验证在线接入

生成召回产物后，启动项目：

```powershell
docker compose up -d --build
```

查看服务状态：

```powershell
docker compose ps
```

查看 Java 是否加载召回产物：

```powershell
docker compose logs java --tail 300
```

日志中应能看到类似：

```text
Loaded ItemCF similarity
Loaded SeqCF transitions
Loaded EASE similarity
Loaded UserCF similarity
```

浏览器访问：

```text
http://localhost:8088
```

登录测试用户：

```text
邮箱: test@rec.dev
密码: test123456
```

打开浏览器开发者工具，查看：

```text
Network -> /api/recommendations/recommend -> Response
```

返回结果中每个推荐项会包含：

```json
{
  "movieId": 1,
  "title": "...",
  "score": 0.123,
  "recallType": "ease"
}
```

如果 `recallType` 中出现：

```text
ease
seqcf
itemcf
usercf
swing
youtubednn
```

说明召回层已经在线接入。

## 7. 关于网页上 100% match 的说明

当前前端电影卡片中的：

```text
100% match
```

不是类型匹配率，也不是召回层计算出的“偏好匹配度”。

前端目前只是直接显示：

```text
movie.score * 100
```

如果后端返回 `score = 1.0`，页面就会显示 `100% match`。

此外，当前排序层的 DeepFM 接口仍是 mock：

```text
inference-service/main.py
```

其中 CTR 分数是随机生成的，不是真正训练后的排序模型。因此如果出现“选择 Animation / Children's，但页面推荐 Action 且显示 100% match”，主要原因不是召回层，而是：

```text
1. 前端 match 展示不是类型匹配率；
2. 冷启动策略可能默认 Action；
3. 排序层 DeepFM 目前仍是 mock CTR；
4. 偏好类型没有在排序层做强约束或显式加权。
```

建议后续排序层同学补充：

```text
GenrePreferenceRankingStrategy
```

或者在 DeepFM 特征中加入用户偏好类型与电影类型的交叉特征。

## 8. 本次召回层边界

已完成：

```text
离线召回实验
多路召回算法实现
召回产物生成脚本
Java 在线召回策略接入
加权 RRF 多路融合
YouTubeDNN 召回辅助接入
召回层指标评测
```

暂不属于召回层范围：

```text
前端 match 文案计算
冷启动默认类型策略
真实 DeepFM 排序模型训练
排序层偏好强约束
最终推荐列表的重排展示逻辑
```

## 9. 推荐汇报表述

可以这样描述本次工作：

```text
我完成了推荐系统召回层的离线实验与在线接入。离线部分实现了 Popular、ItemCF、SeqCF、EASE、Swing、UserCF、Content、Genre、PyTorch YouTubeDNN 等召回方法，并用 Recall、Precision、NDCG、HitRate、Coverage 进行评测。在线部分将 ItemCF、SeqCF、EASE、Swing、UserCF、Popular、UserPreference、PyTorch YouTubeDNN 接入 Java RecallStrategy，并通过加权 RRF 进行多路融合。最终同口径离线 Recall@100 从 0.4015 提升到 0.4687，NDCG@100 从 0.2205 提升到 0.2725。
```
