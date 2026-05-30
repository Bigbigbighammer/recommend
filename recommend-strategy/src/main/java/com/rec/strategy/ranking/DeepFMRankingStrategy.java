package com.rec.strategy.ranking;

import com.rec.common.model.pipeline.CTRPrediction;
import com.rec.common.model.pipeline.ItemFeatures;
import com.rec.common.model.pipeline.RankedItem;
import com.rec.common.model.pipeline.RankingRequest;
import com.rec.common.model.pipeline.RecallItem;
import com.rec.rpc.ModelInferenceClient;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;

import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Component
@ConditionalOnProperty(name = "recommend.strategy.ranking.deepfm.enabled", havingValue = "true", matchIfMissing = true)
public class DeepFMRankingStrategy implements RankingStrategy {

    private final ModelInferenceClient rpcClient;

    public DeepFMRankingStrategy(ModelInferenceClient rpcClient) {
        this.rpcClient = rpcClient;
    }

    @Override
    public String getName() {
        return "deepfm";
    }

    @Override
    public Mono<List<RankedItem>> rank(List<RecallItem> candidates, Map<String, Object> userFeatures,
                                       Map<Long, ItemFeatures> itemFeaturesMap) {
        List<Map<String, Object>> itemFeatureList = candidates.stream()
                .map(c -> {
                    ItemFeatures feats = itemFeaturesMap.get(c.movieId());
                    Map<String, Object> feat = new HashMap<>();
                    feat.put("movie_id", c.movieId());
                    feat.put("genres", feats != null ? feats.genre() : null);
                    feat.put("isAdult", feats != null ? feats.isAdult() : 0);
                    return feat;
                })
                .collect(Collectors.toList());

        var request = new RankingRequest(userFeatures, itemFeatureList, null);

        return rpcClient.predictCTR(request)
                .map(predictions -> {
                    Map<Long, Float> ctrMap = predictions.stream()
                            .collect(Collectors.toMap(CTRPrediction::movieId, CTRPrediction::ctrScore));
                    return candidates.stream()
                            .map(c -> {
                                ItemFeatures feats = itemFeaturesMap.get(c.movieId());
                                float ctr = ctrMap.getOrDefault(c.movieId(), (float) c.score());
                                return new RankedItem(c.movieId(), ctr, c.score(), c.recallType(),
                                        feats != null ? feats.genresList() : List.of(),
                                        feats != null ? feats.year() : 0);
                            })
                            .sorted(Comparator.comparingDouble(RankedItem::score).reversed())
                            .collect(Collectors.toList());
                });
    }
}
