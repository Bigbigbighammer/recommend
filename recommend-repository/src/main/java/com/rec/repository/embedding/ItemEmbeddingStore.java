package com.rec.repository.embedding;

import com.rec.common.model.pipeline.RecallItem;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.util.*;

@Component
public class ItemEmbeddingStore {
    private static final Logger log = LoggerFactory.getLogger(ItemEmbeddingStore.class);

    private final Map<Long, double[]> embeddings;
    private final int dimension;

    public ItemEmbeddingStore(
            @Value("${recommend.embedding.item-emb-path}") String embPath,
            @Value("${recommend.embedding.movie-ids-path}") String idsPath) throws IOException {

        double[][] emb = NpyReader.loadFloat64(embPath);
        long[] ids = NpyReader.loadInt64(idsPath);

        if (emb.length != ids.length) {
            throw new IllegalStateException(
                "Embedding count mismatch: " + emb.length + " vs " + ids.length + " movie IDs");
        }

        this.dimension = emb.length > 0 ? emb[0].length : 0;
        this.embeddings = new HashMap<>(emb.length);

        for (int i = 0; i < emb.length; i++) {
            embeddings.put(ids[i], emb[i]);
        }

        log.info("Loaded {} item embeddings, dimension={}", embeddings.size(), dimension);
    }

    public List<RecallItem> topK(List<Double> userVector, int k, Set<Long> excludeIds, String recallType) {
        if (userVector == null || userVector.size() != dimension) {
            log.warn("User vector dimension mismatch: expected {}, got {}",
                dimension, userVector != null ? userVector.size() : 0);
            return List.of();
        }

        double[] uv = new double[dimension];
        for (int i = 0; i < dimension; i++) {
            uv[i] = userVector.get(i);
        }

        PriorityQueue<RecallItem> heap = new PriorityQueue<>(
            Comparator.comparingDouble(RecallItem::score));

        for (var entry : embeddings.entrySet()) {
            long movieId = entry.getKey();
            if (excludeIds.contains(movieId)) continue;

            double score = dot(uv, entry.getValue());
            if (heap.size() < k) {
                heap.offer(new RecallItem(movieId, score, recallType));
            } else if (score > heap.peek().score()) {
                heap.poll();
                heap.offer(new RecallItem(movieId, score, recallType));
            }
        }

        List<RecallItem> result = new ArrayList<>(heap);
        result.sort((a, b) -> Double.compare(b.score(), a.score()));
        return result;
    }

    static double dot(double[] a, double[] b) {
        double sum = 0;
        for (int i = 0; i < a.length; i++) {
            sum += a[i] * b[i];
        }
        return sum;
    }

    public int getDimension() {
        return dimension;
    }
}
