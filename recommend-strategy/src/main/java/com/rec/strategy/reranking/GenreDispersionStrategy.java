package com.rec.strategy.reranking;

import com.rec.common.model.pipeline.RankedItem;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

@Component
@ConditionalOnProperty(name = "recommend.strategy.reranking.genre-dispersion.enabled", havingValue = "true", matchIfMissing = true)
public class GenreDispersionStrategy implements RerankingStrategy {

    private static final int MAX_CONSECUTIVE = 2;

    @Override
    public String getName() {
        return "genre_dispersion";
    }

    @Override
    public Mono<List<RankedItem>> rerank(List<RankedItem> items, Map<String, Object> userFeatures) {
        if (items.size() <= MAX_CONSECUTIVE) {
            return Mono.just(new ArrayList<>(items));
        }

        List<RankedItem> result = new ArrayList<>();
        List<RankedItem> deferred = new ArrayList<>();

        for (RankedItem item : items) {
            if (canAdd(item, result)) {
                result.add(item);
                tryInsertDeferred(result, deferred);
            } else {
                deferred.add(item);
            }
        }
        result.addAll(deferred);
        return Mono.just(result);
    }

    private boolean canAdd(RankedItem item, List<RankedItem> result) {
        if (result.size() < MAX_CONSECUTIVE) return true;
        List<String> itemGenres = item.genres();
        if (itemGenres == null || itemGenres.isEmpty()) return true;

        String key = itemGenres.get(0);
        int check = Math.min(MAX_CONSECUTIVE - 1, result.size());
        for (int i = result.size() - 1; i >= result.size() - check; i--) {
            List<String> prevGenres = result.get(i).genres();
            if (prevGenres == null || prevGenres.isEmpty()) return true;
            if (!key.equals(prevGenres.get(0))) return true;
        }
        return false;
    }

    private void tryInsertDeferred(List<RankedItem> result, List<RankedItem> deferred) {
        for (int i = deferred.size() - 1; i >= 0; i--) {
            if (canAdd(deferred.get(i), result)) {
                result.add(deferred.remove(i));
            }
        }
    }
}
