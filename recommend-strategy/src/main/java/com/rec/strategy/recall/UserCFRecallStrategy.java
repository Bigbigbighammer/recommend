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
@ConditionalOnProperty(name = "recommend.strategy.recall.usercf.enabled", havingValue = "true", matchIfMissing = true)
public class UserCFRecallStrategy implements RecallStrategy {

    private static final Logger log = LoggerFactory.getLogger(UserCFRecallStrategy.class);

    private final Map<Long, List<NeighborUser>> userSimilarity;
    private final Map<Long, List<Long>> userPositiveItems;

    public UserCFRecallStrategy(
            @Value("${recommend.recall-artifacts.usercf-sim-path:/app/data/usercf_sim.csv}") String simPath,
            @Value("${recommend.recall-artifacts.usercf-items-path:/app/data/user_positive_items.csv}") String itemsPath) {
        this.userSimilarity = loadUserSimilarity(simPath);
        this.userPositiveItems = loadUserPositiveItems(itemsPath);
    }

    @Override
    public String getName() {
        return "usercf";
    }

    @Override
    public Mono<List<RecallItem>> recall(Map<String, Object> userFeatures, int topK) {
        return Mono.fromCallable(() -> {
            Long userId = RecallFeatureUtil.userId(userFeatures);
            if (userId == null || userSimilarity.isEmpty() || userPositiveItems.isEmpty()) {
                return List.<RecallItem>of();
            }

            List<Long> histMovieIds = RecallFeatureUtil.history(userFeatures);
            Set<Long> seen = new HashSet<>(histMovieIds);
            Map<Long, Double> scores = new HashMap<>();

            for (NeighborUser neighbor : userSimilarity.getOrDefault(userId, List.of())) {
                for (Long movieId : userPositiveItems.getOrDefault(neighbor.userId(), List.of())) {
                    if (!seen.contains(movieId)) {
                        scores.merge(movieId, neighbor.score(), Double::sum);
                    }
                }
            }

            return scores.entrySet().stream()
                .sorted(Map.Entry.<Long, Double>comparingByValue().reversed())
                .limit(topK)
                .map(entry -> new RecallItem(entry.getKey(), entry.getValue(), getName()))
                .toList();
        });
    }

    private Map<Long, List<NeighborUser>> loadUserSimilarity(String filePath) {
        Path path = Path.of(filePath);
        if (!Files.exists(path)) {
            log.warn("UserCF similarity file not found: {}", filePath);
            return Map.of();
        }

        Map<Long, List<NeighborUser>> result = new HashMap<>();
        try {
            List<String> lines = Files.readAllLines(path);
            for (int i = 1; i < lines.size(); i++) {
                String[] parts = lines.get(i).split(",");
                if (parts.length < 4) {
                    continue;
                }
                long userId = Long.parseLong(parts[0]);
                long relatedUserId = Long.parseLong(parts[1]);
                double score = Double.parseDouble(parts[3]);
                result.computeIfAbsent(userId, ignored -> new ArrayList<>())
                    .add(new NeighborUser(relatedUserId, score));
            }
            result.values().forEach(items ->
                items.sort(Comparator.comparingDouble(NeighborUser::score).reversed()));
            log.info("Loaded UserCF similarity for {} users from {}", result.size(), filePath);
            return result;
        } catch (IOException | RuntimeException e) {
            log.error("Failed to load UserCF similarity from {}: {}", filePath, e.getMessage());
            return Map.of();
        }
    }

    private Map<Long, List<Long>> loadUserPositiveItems(String filePath) {
        Path path = Path.of(filePath);
        if (!Files.exists(path)) {
            log.warn("User positive items file not found: {}", filePath);
            return Map.of();
        }

        Map<Long, List<Long>> result = new HashMap<>();
        try {
            List<String> lines = Files.readAllLines(path);
            for (int i = 1; i < lines.size(); i++) {
                String[] parts = lines.get(i).split(",");
                if (parts.length < 3) {
                    continue;
                }
                long userId = Long.parseLong(parts[0]);
                long movieId = Long.parseLong(parts[1]);
                result.computeIfAbsent(userId, ignored -> new ArrayList<>()).add(movieId);
            }
            log.info("Loaded positive item lists for {} users from {}", result.size(), filePath);
            return result;
        } catch (IOException | RuntimeException e) {
            log.error("Failed to load positive item lists from {}: {}", filePath, e.getMessage());
            return Map.of();
        }
    }

    private record NeighborUser(long userId, double score) {
    }
}
