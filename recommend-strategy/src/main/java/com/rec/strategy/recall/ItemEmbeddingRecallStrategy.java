package com.rec.strategy.recall;

import com.rec.common.model.pipeline.RecallItem;
import com.rec.repository.embedding.ItemEmbeddingStore;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;

import java.util.Comparator;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

@Component
@ConditionalOnProperty(name = "recommend.strategy.recall.item-embedding.enabled", havingValue = "true", matchIfMissing = true)
public class ItemEmbeddingRecallStrategy implements RecallStrategy {

    private static final Logger log = LoggerFactory.getLogger(ItemEmbeddingRecallStrategy.class);

    private final ItemEmbeddingStore embeddingStore;

    public ItemEmbeddingRecallStrategy(ItemEmbeddingStore embeddingStore) {
        this.embeddingStore = embeddingStore;
    }

    @Override
    public String getName() {
        return "item_embedding";
    }

    @Override
    public Mono<List<RecallItem>> recall(Map<String, Object> userFeatures, int topK) {
        return Mono.<List<RecallItem>>fromCallable(() -> {
            List<Long> histMovieIds = RecallFeatureUtil.history(userFeatures);
            if (histMovieIds.isEmpty()) {
                return List.of();
            }

            Set<Long> seen = new HashSet<>(histMovieIds);
            int seedCount = Math.min(3, histMovieIds.size());
            Map<Long, RecallItem> merged = new LinkedHashMap<>();
            double decay = 1.0;
            for (int s = 0; s < seedCount; s++) {
                Long seedMovieId = histMovieIds.get(histMovieIds.size() - 1 - s);
                List<RecallItem> neighbors = embeddingStore.findSimilarItems(seedMovieId, topK, seen, getName());
                for (RecallItem item : neighbors) {
                    merged.merge(item.movieId(),
                        new RecallItem(item.movieId(), item.score() * decay, getName()),
                        (a, b) -> new RecallItem(a.movieId(), a.score() + b.score(), getName()));
                }
                decay *= 0.6;
            }

            return merged.values().stream()
                .sorted(Comparator.comparingDouble(RecallItem::score).reversed())
                .limit(topK)
                .toList();
        }).onErrorResume(e -> {
            log.error("ItemEmbedding recall failed: {}", e.getMessage());
            return Mono.just(List.of());
        });
    }
}
