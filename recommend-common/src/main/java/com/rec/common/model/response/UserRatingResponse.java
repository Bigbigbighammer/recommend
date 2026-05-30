package com.rec.common.model.response;

public record UserRatingResponse(
    Integer rating,
    boolean hasRated
) {}
