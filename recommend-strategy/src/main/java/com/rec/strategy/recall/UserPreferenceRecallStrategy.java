package com.rec.strategy.recall;

import com.rec.common.model.pipeline.RecallItem;
import com.rec.repository.es.MovieSearchRepository;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;

import java.util.*;

@Component
@ConditionalOnProperty(name = "recommend.strategy.recall.user-preference.enabled", havingValue = "true", matchIfMissing = true)
public class UserPreferenceRecallStrategy implements RecallStrategy {

    private final MovieSearchRepository esRepo;

    public UserPreferenceRecallStrategy(MovieSearchRepository esRepo) {
        this.esRepo = esRepo;
    }

    @Override
    public String getName() {
        return "user_preference";
    }

    @Override
    public Mono<List<RecallItem>> recall(Map<String, Object> userFeatures, int topK) {
        List<String> genres = extractGenres(userFeatures.get("frequent_genres"));
        return esRepo.searchByGenres(genres, topK)
                .map(r -> new RecallItem(r.movieId(), 0.8, getName()))
                .collectList();
    }

    private static List<String> extractGenres(Object value) {
        if (value instanceof List<?> list) {
            return list.stream().map(Object::toString).toList();
        }
        if (value instanceof String s && !s.isBlank()) {
            return Arrays.stream(s.split(",")).map(String::trim).filter(v -> !v.isEmpty()).toList();
        }
        return List.of();
    }
}
