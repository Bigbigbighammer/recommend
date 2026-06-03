package com.rec.strategy.recall;

import com.rec.common.model.pipeline.RecallItem;
import com.rec.repository.entity.MovieEntity;
import com.rec.repository.mapper.MovieMapper;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;

import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

@Component
@ConditionalOnProperty(name = "recommend.strategy.recall.popular.enabled", havingValue = "true", matchIfMissing = true)
public class PopularRecallStrategy implements RecallStrategy {

    private final MovieMapper movieMapper;

    public PopularRecallStrategy(MovieMapper movieMapper) {
        this.movieMapper = movieMapper;
    }

    @Override
    public String getName() {
        return "popular";
    }

    @Override
    public Mono<List<RecallItem>> recall(Map<String, Object> userFeatures, int topK) {
        return Mono.fromCallable(() -> {
            List<Long> histMovieIds = RecallFeatureUtil.history(userFeatures);
            Set<Long> seen = new HashSet<>(histMovieIds);
            return movieMapper.findPopular(topK * 3).stream()
                .filter(movie -> movie.getMovieId() != null && !seen.contains(movie.getMovieId()))
                .limit(topK)
                .map(movie -> new RecallItem(movie.getMovieId(), score(movie), getName()))
                .toList();
        });
    }

    private static double score(MovieEntity movie) {
        double rating = movie.getAvgRating() != null ? movie.getAvgRating() : 0.0;
        double count = movie.getRatingCount() != null ? movie.getRatingCount() : 0.0;
        return rating * Math.log1p(count);
    }
}
