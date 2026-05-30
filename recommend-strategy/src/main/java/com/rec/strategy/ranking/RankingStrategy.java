package com.rec.strategy.ranking;

import com.rec.common.model.pipeline.ItemFeatures;
import com.rec.common.model.pipeline.RankedItem;
import com.rec.common.model.pipeline.RecallItem;
import reactor.core.publisher.Mono;

import java.util.List;
import java.util.Map;

public interface RankingStrategy {

    String getName();

    Mono<List<RankedItem>> rank(List<RecallItem> candidates, Map<String, Object> userFeatures,
                                Map<Long, ItemFeatures> itemFeaturesMap);
}
