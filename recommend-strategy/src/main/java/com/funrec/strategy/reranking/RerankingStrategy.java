package com.funrec.strategy.reranking;

import com.funrec.common.model.pipeline.RankedItem;
import reactor.core.publisher.Mono;

import java.util.List;
import java.util.Map;

public interface RerankingStrategy {

    String getName();

    Mono<List<RankedItem>> rerank(List<RankedItem> items, Map<String, Object> userFeatures);
}
