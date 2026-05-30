package com.funrec.common.model.pipeline;

public record RecallItem(long movieId, double score, String recallType) {
    public RecallItem withScore(double newScore) {
        return new RecallItem(movieId, newScore, recallType);
    }
}
