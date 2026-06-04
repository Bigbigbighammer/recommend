package com.rec.pipeline;

import com.rec.strategy.registry.RecallStrategyRegistry;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import java.util.List;
import java.util.Arrays;
import java.util.Map;
import java.util.stream.Collectors;

@Component
public class RecallStage {
    private final RecallStrategyRegistry registry;
    private final Map<String, Double> fusionWeights;
    private final int rrfK;

    public RecallStage(
            RecallStrategyRegistry registry,
            @Value("${recommend.recall-fusion.weights:itemcf=1.5,usercf=1.0,ease=1.0,seqcf=1.1,bpr=0.0,swing=0.7,user_preference=0.2,item_embedding=0.2,youtubednn=6.0,popular=0.02}") String weights,
            @Value("${recommend.recall-fusion.rrf-k:60}") int rrfK) {
        this.registry = registry;
        this.fusionWeights = parseWeights(weights);
        this.rrfK = rrfK;
    }

    public Mono<PipelineContext> execute(PipelineContext ctx, int topK) {
        return Flux.fromIterable(registry.getActiveStrategies())
            .flatMap(strategy -> strategy.recall(ctx.userFeatures(), topK)
                .onErrorResume(e -> Mono.just(List.of())))
            .collectList()
            .map(results -> SnakeMergeUtil.weightedRrfMerge(results, fusionWeights, topK, rrfK))
            .map(ctx::withRecallCandidates);
    }

    private static Map<String, Double> parseWeights(String weights) {
        if (weights == null || weights.isBlank()) {
            return Map.of();
        }
        return Arrays.stream(weights.split(","))
            .map(String::trim)
            .filter(v -> !v.isEmpty() && v.contains("="))
            .map(v -> v.split("=", 2))
            .collect(Collectors.toMap(
                pair -> pair[0].trim(),
                pair -> Double.parseDouble(pair[1].trim()),
                (left, right) -> right));
    }
}
