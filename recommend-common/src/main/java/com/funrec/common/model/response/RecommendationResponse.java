package com.funrec.common.model.response;

import java.util.List;

public record RecommendationResponse(
    List<RecommendationItemResponse> items,
    int recallCount,
    String rankingStrategy
) {}
