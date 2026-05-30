package com.rec.common.model.response;

public record CastMemberResponse(
    String personId,
    String name,
    String character,
    String category,
    Integer ordering
) {}
