package com.funrec.strategy.coldstart;

import com.funrec.common.model.pipeline.RecallItem;
import com.funrec.repository.es.MovieSearchRepository;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;

import java.util.List;
import java.util.Map;

@Component
@ConditionalOnProperty(name = "recommend.strategy.coldstart.preferred-genre.enabled", havingValue = "true", matchIfMissing = true)
public class PreferredGenreStrategy implements ColdStartStrategy {

    private final MovieSearchRepository esRepo;

    public PreferredGenreStrategy(MovieSearchRepository esRepo) {
        this.esRepo = esRepo;
    }

    @Override
    public String getName() {
        return "preferred_genre";
    }

    @Override
    public boolean canHandle(Map<String, Object> f) {
        return true;
    }

    @Override
    public int getWeight() {
        return 10;
    }

    @Override
    @SuppressWarnings("unchecked")
    public Mono<List<RecallItem>> recommend(Map<String, Object> userFeatures, int topK) {
        List<String> genres = (List<String>) userFeatures.getOrDefault("preferredGenres", List.of());
        return esRepo.searchByGenres(genres, topK)
                .map(r -> new RecallItem(r.movieId(), 1.0, getName()))
                .collectList();
    }
}
