package com.funrec.strategy.reranking;

import com.funrec.common.model.pipeline.RankedItem;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;

@Component
@ConditionalOnProperty(name = "recommend.strategy.reranking.genre-dispersion.enabled", havingValue = "true", matchIfMissing = true)
public class GenreDispersionStrategy implements RerankingStrategy {

    @Override
    public String getName() {
        return "genre_dispersion";
    }

    @Override
    public Mono<List<RankedItem>> rerank(List<RankedItem> items, Map<String, Object> userFeatures) {
        List<RankedItem> result = new ArrayList<>(items);
        List<RankedItem> deferred = new ArrayList<>();
        for (int i = 0; i < result.size(); i++) {
            if (sameGenreCount(result, i) >= 2) {
                deferred.add(result.remove(i));
                i--;
            }
        }
        result.addAll(deferred);
        return Mono.just(result);
    }

    private int sameGenreCount(List<RankedItem> items, int pos) {
        if (pos < 1) {
            return 0;
        }
        var current = items.get(pos).genres();
        int count = 0;
        for (int i = pos - 1; i >= 0 && i >= pos - 2; i--) {
            if (!Collections.disjoint(current, items.get(i).genres())) {
                count++;
            } else {
                break;
            }
        }
        return count;
    }
}
