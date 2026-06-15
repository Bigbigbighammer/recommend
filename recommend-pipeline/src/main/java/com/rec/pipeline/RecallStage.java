package com.rec.pipeline;

import com.rec.common.model.pipeline.RecallItem;
import com.rec.strategy.registry.RecallStrategyRegistry;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

import java.security.SecureRandom;
import java.util.*;
import java.util.stream.Collectors;

@Component
public class RecallStage {
    private final RecallStrategyRegistry registry;
    private final Map<String, Double> fusionWeights;
    private final int rrfK;
    private final SecureRandom rng = new SecureRandom();

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
            .map(results -> channelAwareFusion(results, topK))
            .map(ctx::withRecallCandidates);
    }

    private List<RecallItem> channelAwareFusion(List<List<RecallItem>> resultsList, int topK) {
        List<RecallItem> rrfPool = SnakeMergeUtil.weightedRrfMerge(resultsList, fusionWeights, topK * 2, rrfK);

        int numChannels = (int) resultsList.stream().filter(l -> !l.isEmpty()).count();
        if (numChannels <= 1) {
            return weightedRandomSample(rrfPool, topK);
        }

        Map<String, List<RecallItem>> byChannel = new LinkedHashMap<>();
        for (RecallItem item : rrfPool) {
            byChannel.computeIfAbsent(item.recallType(), k -> new ArrayList<>()).add(item);
        }

        int guaranteedPerChannel = Math.max(1, topK / numChannels);
        int guaranteedTotal = guaranteedPerChannel * byChannel.size();
        int remainderSlots = Math.max(0, topK - guaranteedTotal);

        List<RecallItem> result = new ArrayList<>();

        for (Map.Entry<String, List<RecallItem>> entry : byChannel.entrySet()) {
            List<RecallItem> channelItems = entry.getValue();
            result.addAll(channelItems.subList(0, Math.min(guaranteedPerChannel, channelItems.size())));
        }

        Set<Long> used = new HashSet<>();
        for (RecallItem item : result) used.add(item.movieId());

        List<RecallItem> remaining = new ArrayList<>();
        for (RecallItem item : rrfPool) {
            if (!used.contains(item.movieId())) {
                remaining.add(item);
            }
        }
        result.addAll(weightedRandomSample(remaining, remainderSlots));
        Collections.shuffle(result, rng);
        return result;
    }

    private List<RecallItem> weightedRandomSample(List<RecallItem> candidates, int topK) {
        if (candidates.size() <= topK) {
            return candidates;
        }
        List<RecallItem> shuffled = new ArrayList<>(candidates);
        double totalScore = candidates.stream().mapToDouble(RecallItem::score).sum();
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
