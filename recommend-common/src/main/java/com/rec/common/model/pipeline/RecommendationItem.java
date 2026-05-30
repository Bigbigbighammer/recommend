package com.rec.common.model.pipeline;

public record RecommendationItem(long movieId, double score, String recallType) {}
