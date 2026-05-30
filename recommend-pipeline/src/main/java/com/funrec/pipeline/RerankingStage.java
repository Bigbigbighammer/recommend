package com.funrec.pipeline;

import com.funrec.common.model.pipeline.*;
import com.funrec.strategy.registry.RerankingStrategyRegistry;
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
        for (var strategy : registry.getActiveStrategies()) {
            result = result.flatMap(it ->
                strategy.rerank(it, ctx.userFeatures()).onErrorResume(e -> Mono.just(it)));
        }
        return result.map(ranked -> {
            List<RecommendationItem> recs = ranked.stream()
                .map(r -> new RecommendationItem(r.movieId(), r.score(), r.recallType()))
                .collect(Collectors.toList());
            return ctx.withRerankedItems(recs);
        });
    }
}
