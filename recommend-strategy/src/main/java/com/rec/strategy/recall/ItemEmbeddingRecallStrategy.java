package com.rec.strategy.recall;

import com.rec.common.model.pipeline.RecallItem;
import com.rec.repository.embedding.ItemEmbeddingStore;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;

import java.util.*;

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

            Long queryMovieId = histMovieIds.get(histMovieIds.size() - 1);

            Set<Long> seen = new HashSet<>(histMovieIds);
            return embeddingStore.findSimilarItems(queryMovieId, topK, seen, getName());
        }).onErrorResume(e -> {
            log.error("ItemEmbedding recall failed: {}", e.getMessage());
            return Mono.just(List.of());
        });
    }
}
