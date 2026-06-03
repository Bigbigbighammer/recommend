package com.rec.strategy.recall;

import com.rec.common.model.pipeline.RecallItem;
import com.rec.repository.embedding.NpyReader;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.PriorityQueue;
import java.util.Set;

@Component
@ConditionalOnProperty(name = "recommend.strategy.recall.bpr.enabled", havingValue = "true", matchIfMissing = true)
public class BPRRecallStrategy implements RecallStrategy {

    private static final Logger log = LoggerFactory.getLogger(BPRRecallStrategy.class);

    private final Map<Long, double[]> userEmbeddings;
    private final Map<Long, double[]> itemEmbeddings;
    private final int dimension;

    public BPRRecallStrategy(
            @Value("${recommend.recall-artifacts.bpr-user-emb-path:/app/data/bpr_user_emb.npy}") String userEmbPath,
            @Value("${recommend.recall-artifacts.bpr-user-ids-path:/app/data/bpr_user_ids.npy}") String userIdsPath,
            @Value("${recommend.recall-artifacts.bpr-item-emb-path:/app/data/bpr_item_emb.npy}") String itemEmbPath,
            @Value("${recommend.recall-artifacts.bpr-movie-ids-path:/app/data/bpr_movie_ids.npy}") String movieIdsPath) {
        LoadedEmbeddings loaded = load(userEmbPath, userIdsPath, itemEmbPath, movieIdsPath);
        this.userEmbeddings = loaded.userEmbeddings();
        this.itemEmbeddings = loaded.itemEmbeddings();
        this.dimension = loaded.dimension();
    }

    @Override
    public String getName() {
        return "bpr";
    }

    @Override
    public Mono<List<RecallItem>> recall(Map<String, Object> userFeatures, int topK) {
        return Mono.fromCallable(() -> {
            Long userId = RecallFeatureUtil.userId(userFeatures);
            if (userId == null || userEmbeddings.isEmpty() || itemEmbeddings.isEmpty()) {
                return List.<RecallItem>of();
            }
            double[] userVector = userEmbeddings.get(userId);
            if (userVector == null || userVector.length != dimension) {
                return List.<RecallItem>of();
            }

            Set<Long> seen = new HashSet<>(RecallFeatureUtil.history(userFeatures));
            PriorityQueue<RecallItem> heap = new PriorityQueue<>(Comparator.comparingDouble(RecallItem::score));
            for (var entry : itemEmbeddings.entrySet()) {
                long movieId = entry.getKey();
                if (seen.contains(movieId)) {
                    continue;
                }
                double score = dot(userVector, entry.getValue());
                if (heap.size() < topK) {
                    heap.offer(new RecallItem(movieId, score, getName()));
                } else if (score > heap.peek().score()) {
                    heap.poll();
                    heap.offer(new RecallItem(movieId, score, getName()));
                }
            }

            List<RecallItem> result = new ArrayList<>(heap);
            result.sort((a, b) -> Double.compare(b.score(), a.score()));
            return result;
        });
    }

    private LoadedEmbeddings load(String userEmbPath, String userIdsPath, String itemEmbPath, String movieIdsPath) {
        try {
            double[][] userEmb = NpyReader.loadFloat64(userEmbPath);
            long[] userIds = NpyReader.loadInt64(userIdsPath);
            double[][] itemEmb = NpyReader.loadFloat64(itemEmbPath);
            long[] movieIds = NpyReader.loadInt64(movieIdsPath);
            if (userEmb.length != userIds.length || itemEmb.length != movieIds.length) {
                throw new IllegalStateException("BPR embedding/id count mismatch");
            }
            int dim = itemEmb.length > 0 ? itemEmb[0].length : 0;
            Map<Long, double[]> users = new HashMap<>(userIds.length);
            for (int i = 0; i < userIds.length; i++) {
                users.put(userIds[i], normalize(userEmb[i]));
            }
            Map<Long, double[]> items = new HashMap<>(movieIds.length);
            for (int i = 0; i < movieIds.length; i++) {
                items.put(movieIds[i], normalize(itemEmb[i]));
            }
            log.info("Loaded BPR recall artifacts: users={}, items={}, dim={}", users.size(), items.size(), dim);
            return new LoadedEmbeddings(users, items, dim);
        } catch (IOException | RuntimeException e) {
            log.warn("BPR recall artifacts unavailable: {}", e.getMessage());
            return new LoadedEmbeddings(Map.of(), Map.of(), 0);
        }
    }

    private static double[] normalize(double[] vector) {
        double norm = 0;
        for (double v : vector) {
            norm += v * v;
        }
        norm = Math.sqrt(norm);
        if (norm > 0) {
            for (int i = 0; i < vector.length; i++) {
                vector[i] /= norm;
            }
        }
        return vector;
    }

    private static double dot(double[] a, double[] b) {
        double sum = 0;
        for (int i = 0; i < a.length; i++) {
            sum += a[i] * b[i];
        }
        return sum;
    }

    private record LoadedEmbeddings(
        Map<Long, double[]> userEmbeddings,
        Map<Long, double[]> itemEmbeddings,
        int dimension
    ) {
    }
}
