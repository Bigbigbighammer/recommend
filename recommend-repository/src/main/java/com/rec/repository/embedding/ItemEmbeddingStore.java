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
    private final Map<Long, double[]> youtubednnEmbeddings;
    private final int dimension;
    private final int youtubednnDimension;
    private final boolean hasYouTubeDNN;

    public ItemEmbeddingStore(
            @Value("${recommend.embedding.item-emb-path}") String embPath,
            @Value("${recommend.embedding.movie-ids-path}") String idsPath,
            @Value("${recommend.embedding.youtubednn-item-emb-path:#{null}}") String ytEmbPath,
            @Value("${recommend.embedding.youtubednn-movie-ids-path:#{null}}") String ytIdsPath) throws IOException {

        double[][] emb = NpyReader.loadFloat64(embPath);
        long[] ids = NpyReader.loadInt64(idsPath);

        if (emb.length != ids.length) {
            throw new IllegalStateException(
                "Embedding count mismatch: " + emb.length + " vs " + ids.length + " movie IDs");
        }

        this.dimension = emb.length > 0 ? emb[0].length : 0;
        this.embeddings = new HashMap<>(emb.length);

        for (int i = 0; i < emb.length; i++) {
            double[] vec = emb[i];
            double norm = 0;
            for (double v : vec) norm += v * v;
            norm = Math.sqrt(norm);
            if (norm > 0) {
                for (int j = 0; j < vec.length; j++) {
                    vec[j] /= norm;
                }
            }
            embeddings.put(ids[i], vec);
        }

        log.info("Loaded {} item embeddings (L2-normalized), dimension={}", embeddings.size(), dimension);

        if (ytEmbPath != null && ytIdsPath != null) {
            double[][] ytEmb = NpyReader.loadFloat64(ytEmbPath);
            long[] ytIds = NpyReader.loadInt64(ytIdsPath);
            if (ytEmb.length != ytIds.length) {
                throw new IllegalStateException(
                    "YouTubeDNN embedding count mismatch: " + ytEmb.length + " vs " + ytIds.length);
            }
            this.youtubednnDimension = ytEmb.length > 0 ? ytEmb[0].length : 0;
            this.youtubednnEmbeddings = new HashMap<>(ytEmb.length);
            for (int i = 0; i < ytEmb.length; i++) {
                youtubednnEmbeddings.put(ytIds[i], ytEmb[i]);
            }
            this.hasYouTubeDNN = true;
            log.info("Loaded {} YouTubeDNN item embeddings, dimension={}", youtubednnEmbeddings.size(), youtubednnDimension);
        } else {
            this.youtubednnEmbeddings = null;
            this.youtubednnDimension = 0;
            this.hasYouTubeDNN = false;
            log.info("YouTubeDNN embeddings not configured, recall will use NumPy fallback path");
        }
    }

    public List<RecallItem> topK(List<Double> userVector, int k, Set<Long> excludeIds, String recallType) {
        return topKWithEmbeddings(userVector, k, excludeIds, recallType, embeddings, dimension);
    }

    public List<RecallItem> topKYouTubeDNN(List<Double> userVector, int k, Set<Long> excludeIds, String recallType) {
        if (!hasYouTubeDNN) {
            return topK(userVector, k, excludeIds, recallType);
        }
        return topKWithEmbeddings(userVector, k, excludeIds, recallType, youtubednnEmbeddings, youtubednnDimension);
    }

    private List<RecallItem> topKWithEmbeddings(List<Double> userVector, int k, Set<Long> excludeIds,
                                                  String recallType, Map<Long, double[]> embMap, int dim) {
        if (userVector == null || userVector.size() != dim) {
            log.warn("User vector dimension mismatch: expected {}, got {}",
                dim, userVector != null ? userVector.size() : 0);
            return List.of();
        }

        double[] uv = new double[dim];
        for (int i = 0; i < dim; i++) {
            uv[i] = userVector.get(i);
        }

        PriorityQueue<RecallItem> heap = new PriorityQueue<>(
            Comparator.comparingDouble(RecallItem::score));

        for (var entry : embMap.entrySet()) {
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

    public double[] getEmbedding(long movieId) {
        return embeddings.get(movieId);
    }

    public List<RecallItem> findSimilarItems(long queryMovieId, int k, Set<Long> excludeIds, String recallType) {
        double[] queryEmb = embeddings.get(queryMovieId);
        if (queryEmb == null) {
            log.warn("Query movie {} not found in embedding store", queryMovieId);
            return List.of();
        }

        PriorityQueue<RecallItem> heap = new PriorityQueue<>(
            Comparator.comparingDouble(RecallItem::score));

        for (var entry : embeddings.entrySet()) {
            long movieId = entry.getKey();
            if (movieId == queryMovieId) continue;
            if (excludeIds.contains(movieId)) continue;

            double score = dot(queryEmb, entry.getValue());
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

    public int getDimension() {
        return dimension;
    }
}
