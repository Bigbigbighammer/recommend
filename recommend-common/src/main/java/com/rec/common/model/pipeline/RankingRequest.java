package com.rec.common.model.pipeline;

import com.fasterxml.jackson.databind.annotation.JsonNaming;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;

import java.util.List;
import java.util.Map;

@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record RankingRequest(
    Map<String, Object> userFeatures,
    List<Map<String, Object>> itemFeatures,
    String modelVersion
) {}
