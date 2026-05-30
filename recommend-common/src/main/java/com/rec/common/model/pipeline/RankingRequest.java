package com.rec.common.model.pipeline;

import java.util.List;
import java.util.Map;

public record RankingRequest(
    Map<String, Object> userFeatures,
    List<Map<String, Object>> itemFeatures,
    String modelVersion
) {}
