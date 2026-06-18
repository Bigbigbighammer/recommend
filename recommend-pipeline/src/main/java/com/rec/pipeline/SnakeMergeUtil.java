package com.rec.pipeline;

import com.rec.common.model.pipeline.RecallItem;
import java.util.*;

public final class SnakeMergeUtil {

    private SnakeMergeUtil() {}

    public static List<RecallItem> snakeMerge(List<List<RecallItem>> resultsList, int topK) {
        if (resultsList.isEmpty()) return List.of();
        Set<Long> seen = new HashSet<>();
        List<RecallItem> merged = new ArrayList<>();
        int maxLen = resultsList.stream().mapToInt(List::size).max().orElse(0);
        for (int i = 0; i < maxLen; i++) {
            for (int j = 0; j < resultsList.size(); j++) {
                List<RecallItem> list = resultsList.get(j);
                int idx = (j % 2 == 0) ? i : (list.size() - 1 - i);
                if (idx >= 0 && idx < list.size()) {
                    RecallItem item = list.get(idx);
                    if (seen.add(item.movieId())) {
                        merged.add(item);
                        if (merged.size() >= topK) return merged;
                    }
                }
            }
        }
        return merged;
    }

    public static List<RecallItem> roundRobinMerge(List<List<RecallItem>> resultsList, int topK) {
        if (resultsList.isEmpty()) return List.of();
        Set<Long> seen = new HashSet<>();
        List<RecallItem> merged = new ArrayList<>();
        int maxLen = resultsList.stream().mapToInt(List::size).max().orElse(0);
        for (int i = 0; i < maxLen; i++) {
            for (List<RecallItem> list : resultsList) {
                if (i < list.size()) {
                    RecallItem item = list.get(i);
                    if (seen.add(item.movieId())) {
                        merged.add(item);
                        if (merged.size() >= topK) return merged;
                    }
                }
            }
        }
        return merged;
    }

    public static List<RecallItem> weightedRrfMerge(
            List<List<RecallItem>> resultsList,
            Map<String, Double> weights,
            int topK,
            int rrfK) {
        if (resultsList.isEmpty()) return List.of();

        double maxWeight = weights.values().stream().mapToDouble(Double::doubleValue).max().orElse(1.0);

        Map<Long, Double> scores = new HashMap<>();
        Map<Long, String> recallTypes = new HashMap<>();
        for (List<RecallItem> list : resultsList) {
            if (list.isEmpty()) continue;
            String strategy = list.get(0).recallType();
            double weight = weights.getOrDefault(strategy, 1.0);
            if (weight <= 0) continue;

            int cap = (int) Math.max(10, topK * weight / maxWeight);
            int limit = Math.min(list.size(), cap);

            for (int rank = 0; rank < limit; rank++) {
                RecallItem item = list.get(rank);
                scores.merge(item.movieId(), weight / (rrfK + rank + 1.0), Double::sum);
                recallTypes.putIfAbsent(item.movieId(), item.recallType());
            }
        }

        return scores.entrySet().stream()
            .sorted(Map.Entry.<Long, Double>comparingByValue().reversed())
            .limit(topK)
            .map(entry -> new RecallItem(
                entry.getKey(),
                entry.getValue(),
                recallTypes.getOrDefault(entry.getKey(), "fusion")))
            .toList();
    }
}
