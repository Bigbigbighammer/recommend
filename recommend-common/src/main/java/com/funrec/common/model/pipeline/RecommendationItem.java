package com.funrec.common.model.pipeline;

public record RecommendationItem(long movieId, double score, String recallType) {}
