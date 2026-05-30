package com.funrec.pipeline;

import com.funrec.common.model.pipeline.RecallItem;
import com.funrec.strategy.coldstart.ColdStartStrategy;
import com.funrec.strategy.registry.ColdStartStrategyRegistry;
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
                .map(items -> items))
            .collectList()
            .map(results -> {
                List<RecallItem> merged = SnakeMergeUtil.roundRobinMerge(results, topK);
                return ctx.withRecallCandidates(merged);
            });
    }
}
