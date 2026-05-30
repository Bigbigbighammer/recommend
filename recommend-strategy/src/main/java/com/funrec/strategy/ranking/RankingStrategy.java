package com.funrec.strategy.ranking;

import com.funrec.common.model.pipeline.ItemFeatures;
import com.funrec.common.model.pipeline.RankedItem;
import com.funrec.common.model.pipeline.RecallItem;
import reactor.core.publisher.Mono;

import java.util.List;
import java.util.Map;

public interface RankingStrategy {

    String getName();

    Mono<List<RankedItem>> rank(List<RecallItem> candidates, Map<String, Object> userFeatures,
                                Map<Long, ItemFeatures> itemFeaturesMap);
}
