package com.rec.common.model.pipeline;

import java.util.List;
import java.util.Map;

public record RecallRequest(
    Map<String, Object> userFeatures,
    List<Long> histMovieIds,
    String modelVersion
) {}
