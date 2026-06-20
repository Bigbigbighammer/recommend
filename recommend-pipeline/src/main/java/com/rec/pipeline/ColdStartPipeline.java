package com.rec.pipeline;

import com.rec.common.model.pipeline.RecallItem;
import com.rec.common.model.pipeline.RecommendationItem;
import com.rec.strategy.coldstart.ColdStartStrategy;
import com.rec.strategy.registry.ColdStartStrategyRegistry;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import java.security.SecureRandom;
import java.util.*;
import java.util.stream.Collectors;

@Component
public class ColdStartPipeline {
    private final ColdStartStrategyRegistry registry;
    private final SecureRandom rng = new SecureRandom();

    public ColdStartPipeline(ColdStartStrategyRegistry registry) {
        this.registry = registry;
    }

    public Mono<PipelineContext> execute(PipelineContext ctx, int topK) {
        int poolSize = Math.max(topK * 3, 60);
        List<ColdStartStrategy> strategies = registry.getActiveStrategies();
        return Flux.fromIterable(strategies)
            .flatMap(strategy -> strategy.recommend(ctx.userFeatures(), poolSize))
            .collectList()
            .map(results -> {
                List<RecallItem> merged = SnakeMergeUtil.roundRobinMerge(results, Math.min(poolSize * 2, 200));
                List<RecallItem> sampled = weightedRandomSample(merged, topK);
                List<RecommendationItem> recs = sampled.stream()
                    .map(r -> new RecommendationItem(r.movieId(), r.score(), r.recallType()))
                    .collect(Collectors.toList());
                return ctx.withRecallCandidates(sampled).withRerankedItems(recs);
            });
    }

    private List<RecallItem> weightedRandomSample(List<RecallItem> candidates, int topK) {
        if (candidates.size() <= topK) {
            List<RecallItem> list = new ArrayList<>(candidates);
            Collections.shuffle(list, rng);
            return list;
        }
        List<RecallItem> shuffled = new ArrayList<>(candidates);
        double totalScore = shuffled.stream().mapToDouble(RecallItem::score).sum();
        if (totalScore <= 0) {
            Collections.shuffle(shuffled, rng);
            return shuffled.subList(0, topK);
        }
        Map<RecallItem, Double> cumulative = new LinkedHashMap<>(shuffled.size());
        double cum = 0;
        for (RecallItem item : shuffled) {
            cum += item.score() / totalScore;
            cumulative.put(item, cum);
        }
        Set<RecallItem> picked = new LinkedHashSet<>();
        for (int i = 0; i < topK * 2 && picked.size() < topK; i++) {
            double r = rng.nextDouble();
            for (var entry : cumulative.entrySet()) {
                if (r <= entry.getValue()) {
                    picked.add(entry.getKey());
                    break;
                }
            }
        }
        if (picked.size() < topK) {
            for (RecallItem item : shuffled) {
                picked.add(item);
                if (picked.size() >= topK) break;
            }
        }
        return new ArrayList<>(picked);
    }
}
