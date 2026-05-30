package com.rec.common.model.response;

public record RatingResponse(
    Long userId,
    Long movieId,
    Integer rating,
    Long timestamp
) {}
