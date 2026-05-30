package com.funrec.strategy.ranking;

import com.funrec.common.model.pipeline.ItemFeatures;
import com.funrec.common.model.pipeline.RankedItem;
import com.funrec.common.model.pipeline.RecallItem;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;

import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Component
@ConditionalOnProperty(name = "recommend.strategy.ranking.fallback.enabled", havingValue = "true", matchIfMissing = true)
public class FallbackRankingStrategy implements RankingStrategy {

    @Override
    public String getName() {
        return "fallback";
    }

    @Override
    public Mono<List<RankedItem>> rank(List<RecallItem> candidates, Map<String, Object> userFeatures,
                                       Map<Long, ItemFeatures> itemFeaturesMap) {
        return Mono.just(candidates.stream()
                .map(c -> {
                    ItemFeatures feats = itemFeaturesMap.get(c.movieId());
                    return new RankedItem(c.movieId(), c.score(), c.score(), c.recallType(),
                            feats != null ? feats.genresList() : List.of(),
                            feats != null ? feats.year() : 0);
                })
                .sorted(Comparator.comparingDouble(RankedItem::score).reversed())
                .collect(Collectors.toList()));
    }
}
