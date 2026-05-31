package com.rec.strategy.reranking;

import com.rec.common.model.pipeline.RankedItem;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

@Component
@ConditionalOnProperty(name = "recommend.strategy.reranking.decade-dispersion.enabled", havingValue = "true", matchIfMissing = true)
public class DecadeDispersionStrategy implements RerankingStrategy {

    private static final int MAX_CONSECUTIVE = 3;

    @Override
    public String getName() {
        return "decade_dispersion";
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
        int itemDecade = item.year() / 10;
        if (itemDecade < 190 || itemDecade > 210) return true;

        int check = Math.min(MAX_CONSECUTIVE - 1, result.size());
        for (int i = result.size() - 1; i >= result.size() - check; i--) {
            int prevDecade = result.get(i).year() / 10;
            if (prevDecade != itemDecade) return true;
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
