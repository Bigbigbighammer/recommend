package com.rec.strategy.coldstart;

import com.rec.common.model.pipeline.RecallItem;
import com.rec.repository.es.MovieSearchRepository;
import com.rec.repository.redis.UserProfileRedisRepository;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;

import java.util.List;
import java.util.Map;

@Component
@ConditionalOnProperty(name = "recommend.strategy.coldstart.ucb-genre.enabled", havingValue = "true", matchIfMissing = true)
public class UCBGenreStrategy implements ColdStartStrategy {

    private final UserProfileRedisRepository redisRepo;
    private final MovieSearchRepository esRepo;

    public UCBGenreStrategy(UserProfileRedisRepository redisRepo, MovieSearchRepository esRepo) {
        this.redisRepo = redisRepo;
        this.esRepo = esRepo;
    }

    @Override
    public String getName() {
        return "ucb_genre";
    }

    @Override
    public boolean canHandle(Map<String, Object> f) {
        return true;
    }

    @Override
    public int getWeight() {
        return 70;
    }

    @Override
    public Mono<List<RecallItem>> recommend(Map<String, Object> userFeatures, int topK) {
        Long userId = (Long) userFeatures.get("userId");
        if (userId == null) {
            return esRepo.searchByGenres(List.of(), topK)
                    .map(r -> new RecallItem(r.movieId(), 1.0, getName()))
                    .collectList();
        }
        return redisRepo.getUCBStats(userId)
                .flatMap(stats -> {
                    String bestGenre = selectBestGenre(stats);
                    return esRepo.searchByGenres(List.of(bestGenre), topK)
                            .map(r -> new RecallItem(r.movieId(), 1.0, getName()))
                            .collectList();
                })
                .switchIfEmpty(esRepo.searchByGenres(List.of(), topK)
                        .map(r -> new RecallItem(r.movieId(), 1.0, getName()))
                        .collectList());
    }

    private String selectBestGenre(Map<String, Map<String, Integer>> stats) {
        return stats.entrySet().stream()
                .max((a, b) -> {
                    double ucbA = ucb(a.getValue().getOrDefault("n", 0), a.getValue().getOrDefault("reward", 0));
                    double ucbB = ucb(b.getValue().getOrDefault("n", 0), b.getValue().getOrDefault("reward", 0));
                    return Double.compare(ucbA, ucbB);
                })
                .map(Map.Entry::getKey)
                .orElse("Action");
    }

    private double ucb(int n, int reward) {
        if (n == 0) {
            return Double.MAX_VALUE;
        }
        return (double) reward / n + Math.sqrt(2 * Math.log(100) / n);
    }
}
