package com.funrec.strategy.coldstart;

import com.funrec.common.model.pipeline.RecallItem;
import reactor.core.publisher.Mono;

import java.util.List;
import java.util.Map;

public interface ColdStartStrategy {

    String getName();

    boolean canHandle(Map<String, Object> userFeatures);

    int getWeight();

    Mono<List<RecallItem>> recommend(Map<String, Object> userFeatures, int topK);
}
