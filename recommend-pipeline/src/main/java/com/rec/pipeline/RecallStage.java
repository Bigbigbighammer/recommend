package com.rec.pipeline;

import com.rec.strategy.registry.RecallStrategyRegistry;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import java.util.List;

@Component
public class RecallStage {
    private final RecallStrategyRegistry registry;

    public RecallStage(RecallStrategyRegistry registry) {
        this.registry = registry;
    }

    public Mono<PipelineContext> execute(PipelineContext ctx, int topK) {
        return Flux.fromIterable(registry.getActiveStrategies())
            .flatMap(strategy -> strategy.recall(ctx.userFeatures(), topK)
                .onErrorResume(e -> Mono.just(List.of())))
            .collectList()
            .map(results -> SnakeMergeUtil.snakeMerge(results, topK))
            .map(ctx::withRecallCandidates);
    }
}
