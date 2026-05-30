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
}
