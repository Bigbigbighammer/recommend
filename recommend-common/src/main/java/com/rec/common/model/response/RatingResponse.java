package com.rec.common.model.response;

public record RatingResponse(
    Long userId,
    Long movieId,
    String title,
    Integer rating,
    Long timestamp
) {}
