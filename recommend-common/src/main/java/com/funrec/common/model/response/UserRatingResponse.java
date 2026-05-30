package com.funrec.common.model.response;

public record UserRatingResponse(
    Integer rating,
    boolean hasRated
) {}
