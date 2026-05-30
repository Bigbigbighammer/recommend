package com.funrec.common.model.response;

public record RatingResponse(
    Long userId,
    Long movieId,
    Integer rating,
    Long timestamp
) {}
