package com.rec.pipeline;

import com.rec.common.model.pipeline.RecallItem;
import com.rec.common.model.pipeline.RecommendationItem;
import com.rec.strategy.coldstart.ColdStartStrategy;
import com.rec.strategy.registry.ColdStartStrategyRegistry;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import java.util.List;
import java.util.stream.Collectors;

@Component
public class ColdStartPipeline {
    private final ColdStartStrategyRegistry registry;

    public ColdStartPipeline(ColdStartStrategyRegistry registry) {
        this.registry = registry;
    }

    public Mono<PipelineContext> execute(PipelineContext ctx, int topK) {
        List<ColdStartStrategy> strategies = registry.getActiveStrategies();
        return Flux.fromIterable(strategies)
            .flatMap(strategy -> strategy.recommend(ctx.userFeatures(), topK))
            .collectList()
            .map(results -> {
                List<RecallItem> merged = SnakeMergeUtil.roundRobinMerge(results, topK);
                List<RecommendationItem> recs = merged.stream()
                    .map(r -> new RecommendationItem(r.movieId(), r.score(), r.recallType()))
                    .collect(Collectors.toList());
                return ctx.withRecallCandidates(merged).withRerankedItems(recs);
            });
    }
}
