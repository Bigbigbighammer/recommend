package com.funrec.pipeline;

import com.funrec.common.model.pipeline.*;
import java.util.*;

public record PipelineContext(
    Map<String, Object> userFeatures,
    List<Long> histMovieIds,
    boolean isColdStart,
    List<RecallItem> recallCandidates,
    Map<Long, ItemFeatures> itemFeaturesMap,
    List<RankedItem> rankedItems,
    List<RecommendationItem> rerankedItems
) {
    public static PipelineContext initial(Map<String, Object> userFeatures) {
        return new PipelineContext(new HashMap<>(userFeatures), List.of(), false,
            List.of(), Map.of(), List.of(), List.of());
    }

    public PipelineContext withUserFeatures(Map<String, Object> enriched) {
        Map<String, Object> merged = new HashMap<>(this.userFeatures);
        merged.putAll(enriched);
        return new PipelineContext(merged, histMovieIds, isColdStart,
            recallCandidates, itemFeaturesMap, rankedItems, rerankedItems);
    }

    public PipelineContext withHistMovieIds(List<Long> ids) {
        return new PipelineContext(userFeatures, ids, isColdStart,
            recallCandidates, itemFeaturesMap, rankedItems, rerankedItems);
    }

    public PipelineContext withColdStart(boolean coldStart) {
        return new PipelineContext(userFeatures, histMovieIds, coldStart,
            recallCandidates, itemFeaturesMap, rankedItems, rerankedItems);
    }

    public PipelineContext withRecallCandidates(List<RecallItem> candidates) {
        return new PipelineContext(userFeatures, histMovieIds, isColdStart,
            candidates, itemFeaturesMap, rankedItems, rerankedItems);
    }

    public PipelineContext withItemFeatures(Map<Long, ItemFeatures> features) {
        return new PipelineContext(userFeatures, histMovieIds, isColdStart,
            recallCandidates, features, rankedItems, rerankedItems);
    }

    public PipelineContext withRankedItems(List<RankedItem> items) {
        return new PipelineContext(userFeatures, histMovieIds, isColdStart,
            recallCandidates, itemFeaturesMap, items, rerankedItems);
    }

    public PipelineContext withRerankedItems(List<RecommendationItem> items) {
        return new PipelineContext(userFeatures, histMovieIds, isColdStart,
            recallCandidates, itemFeaturesMap, rankedItems, items);
    }
}
