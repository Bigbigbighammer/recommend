package com.funrec.strategy.recall;

import com.funrec.common.model.pipeline.RecallItem;
import com.funrec.common.model.pipeline.RecallRequest;
import com.funrec.rpc.ModelInferenceClient;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;

import java.util.List;
import java.util.Map;

@Component
@ConditionalOnProperty(name = "recommend.strategy.recall.item-embedding.enabled", havingValue = "true", matchIfMissing = false)
public class ItemEmbeddingRecallStrategy implements RecallStrategy {

    private final ModelInferenceClient rpcClient;

    public ItemEmbeddingRecallStrategy(ModelInferenceClient rpcClient) {
        this.rpcClient = rpcClient;
    }

    @Override
    public String getName() {
        return "item_embedding";
    }

    @Override
    @SuppressWarnings("unchecked")
    public Mono<List<RecallItem>> recall(Map<String, Object> userFeatures, int topK) {
        var request = new RecallRequest(userFeatures,
                (List<Long>) userFeatures.getOrDefault("histMovieIds", List.of()), null);
        return rpcClient.generateUserVector(request)
                .then(Mono.just(List.of()));
    }
}
