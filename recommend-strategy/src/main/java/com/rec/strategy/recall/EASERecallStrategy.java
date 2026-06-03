package com.rec.strategy.recall;

import com.rec.common.model.pipeline.RecallItem;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

@Component
@ConditionalOnProperty(name = "recommend.strategy.recall.ease.enabled", havingValue = "true", matchIfMissing = true)
public class EASERecallStrategy implements RecallStrategy {

    private static final Logger log = LoggerFactory.getLogger(EASERecallStrategy.class);

    private final Map<Long, List<Neighbor>> similarity;

    public EASERecallStrategy(
            @Value("${recommend.recall-artifacts.ease-path:/app/data/ease_sim.csv}") String path) {
        this.similarity = loadSimilarity(path);
    }

    @Override
    public String getName() {
        return "ease";
    }

    @Override
    public Mono<List<RecallItem>> recall(Map<String, Object> userFeatures, int topK) {
        return Mono.fromCallable(() -> {
            if (similarity.isEmpty()) {
                return List.<RecallItem>of();
            }

            List<Long> histMovieIds = RecallFeatureUtil.history(userFeatures);
            if (histMovieIds.isEmpty()) {
                return List.<RecallItem>of();
            }

            Set<Long> seen = new HashSet<>(histMovieIds);
            Map<Long, Double> scores = new HashMap<>();
            int start = Math.max(0, histMovieIds.size() - 80);
            int rank = 0;
            for (int i = histMovieIds.size() - 1; i >= start; i--) {
                Long movieId = histMovieIds.get(i);
                double decay = 1.0 / (1.0 + 0.04 * rank);
                for (Neighbor neighbor : similarity.getOrDefault(movieId, List.of())) {
                    if (!seen.contains(neighbor.movieId())) {
                        scores.merge(neighbor.movieId(), neighbor.score() * decay, Double::sum);
                    }
                }
                rank++;
            }

            return scores.entrySet().stream()
                .sorted(Map.Entry.<Long, Double>comparingByValue().reversed())
                .limit(topK)
                .map(entry -> new RecallItem(entry.getKey(), entry.getValue(), getName()))
                .toList();
        });
    }

    private Map<Long, List<Neighbor>> loadSimilarity(String filePath) {
        Path path = Path.of(filePath);
        if (!Files.exists(path)) {
            log.warn("EASE similarity file not found: {}", filePath);
            return Map.of();
        }

        Map<Long, List<Neighbor>> result = new HashMap<>();
        try {
            List<String> lines = Files.readAllLines(path);
            for (int i = 1; i < lines.size(); i++) {
                String[] parts = lines.get(i).split(",");
                if (parts.length < 4) {
                    continue;
                }
                long movieId = Long.parseLong(parts[0]);
                long relatedMovieId = Long.parseLong(parts[1]);
                double score = Double.parseDouble(parts[3]);
                result.computeIfAbsent(movieId, ignored -> new ArrayList<>())
                    .add(new Neighbor(relatedMovieId, score));
            }
            result.values().forEach(items ->
                items.sort(Comparator.comparingDouble(Neighbor::score).reversed()));
            log.info("Loaded EASE similarity for {} movies from {}", result.size(), filePath);
            return result;
        } catch (IOException | RuntimeException e) {
            log.error("Failed to load EASE similarity from {}: {}", filePath, e.getMessage());
            return Map.of();
        }
    }

    private record Neighbor(long movieId, double score) {
    }
}
