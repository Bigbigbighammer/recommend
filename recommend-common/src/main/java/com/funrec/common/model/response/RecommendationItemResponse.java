package com.funrec.common.model.response;

import java.util.List;

public record RecommendationItemResponse(
    Long movieId,
    String title,
    List<String> genres,
    Double score,
    Double recallScore,
    String recallType,
    String posterUrl
) {}
