package com.funrec.strategy.coldstart;

import com.funrec.common.model.pipeline.RecallItem;
import com.funrec.repository.es.MovieSearchRepository;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;

import java.util.List;
import java.util.Map;

@Component
@ConditionalOnProperty(name = "recommend.strategy.coldstart.popular-recent.enabled", havingValue = "true", matchIfMissing = true)
public class PopularRecentStrategy implements ColdStartStrategy {

    private final MovieSearchRepository esRepo;

    public PopularRecentStrategy(MovieSearchRepository esRepo) {
        this.esRepo = esRepo;
    }

    @Override
    public String getName() {
        return "popular_recent";
    }

    @Override
    public boolean canHandle(Map<String, Object> f) {
        return true;
    }

    @Override
    public int getWeight() {
        return 20;
    }

    @Override
    public Mono<List<RecallItem>> recommend(Map<String, Object> userFeatures, int topK) {
        return esRepo.searchByGenres(List.of(), topK)
                .map(r -> new RecallItem(r.movieId(), 1.0, getName()))
                .collectList();
    }
}
