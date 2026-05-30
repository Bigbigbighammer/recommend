package com.rec.strategy.recall;

import com.rec.common.model.pipeline.RecallItem;
import com.rec.common.model.pipeline.RecallRequest;
import com.rec.repository.embedding.ItemEmbeddingStore;
import com.rec.rpc.ModelInferenceClient;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;

import java.util.*;

@Component
@ConditionalOnProperty(name = "recommend.strategy.recall.youtubednn.enabled", havingValue = "true", matchIfMissing = true)
public class YouTubeDNNRecallStrategy implements RecallStrategy {

    private final ModelInferenceClient rpcClient;
    private final ItemEmbeddingStore embeddingStore;

    public YouTubeDNNRecallStrategy(ModelInferenceClient rpcClient, ItemEmbeddingStore embeddingStore) {
        this.rpcClient = rpcClient;
        this.embeddingStore = embeddingStore;
    }

    @Override
    public String getName() {
        return "youtubednn";
    }

    @Override
    @SuppressWarnings("unchecked")
    public Mono<List<RecallItem>> recall(Map<String, Object> userFeatures, int topK) {
        List<Long> histMovieIds = (List<Long>) userFeatures.getOrDefault("histMovieIds", List.of());
        var request = new RecallRequest(userFeatures, histMovieIds, "");
        return rpcClient.generateUserVector(request)
            .map(resp -> {
                Set<Long> seen = new HashSet<>(histMovieIds);
                return embeddingStore.topK(resp.userVector(), topK, seen, getName());
            })
            .onErrorResume(e -> Mono.just(List.of()));
    }
}
