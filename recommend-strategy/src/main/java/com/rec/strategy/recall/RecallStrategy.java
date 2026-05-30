package com.rec.strategy.recall;

import com.rec.common.model.pipeline.RecallItem;
import reactor.core.publisher.Mono;

import java.util.List;
import java.util.Map;

public interface RecallStrategy {

    String getName();

    Mono<List<RecallItem>> recall(Map<String, Object> userFeatures, int topK);
}
