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

    public RecommendationPipeline(UserFeatureEnrichmentStage enrichment,
                                  ColdStartDetectionStage coldStartDetection,
                                  ColdStartPipeline coldStartPipeline,
                                  RecallStage recallStage,
                                  RankingStage rankingStage,
                                  RerankingStage rerankingStage) {
        this.enrichment = enrichment;
        this.coldStartDetection = coldStartDetection;
        this.coldStartPipeline = coldStartPipeline;
        this.recallStage = recallStage;
        this.rankingStage = rankingStage;
        this.rerankingStage = rerankingStage;
    }

    public Mono<PipelineContext> recommend(Map<String, Object> userFeatures) {
        return Mono.just(PipelineContext.initial(userFeatures))
            .flatMap(enrichment::execute)
            .flatMap(coldStartDetection::execute)
            .flatMap(ctx -> {
                if (ctx.isColdStart()) {
                    return coldStartPipeline.execute(ctx, COLD_START_TOP_K);
                }
                return Mono.just(ctx)
                    .flatMap(c -> recallStage.execute(c, RECALL_TOP_K))
                    .flatMap(c -> rankingStage.execute(c, RANK_TOP_K))
                    .flatMap(rerankingStage::execute);
            })
            .timeout(Duration.ofMillis(5000));
    }
}
