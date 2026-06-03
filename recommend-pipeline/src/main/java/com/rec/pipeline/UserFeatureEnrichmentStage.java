package com.rec.pipeline;

import com.rec.repository.mapper.RatingMapper;
import com.rec.repository.mapper.UserMapper;
import com.rec.repository.redis.UserProfileRedisRepository;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;
import java.util.*;

@Component
public class UserFeatureEnrichmentStage {
    private final UserProfileRedisRepository redisRepo;
    private final UserMapper userMapper;
    private final RatingMapper ratingMapper;

    public UserFeatureEnrichmentStage(UserProfileRedisRepository redisRepo, UserMapper userMapper,
                                      RatingMapper ratingMapper) {
        this.redisRepo = redisRepo;
        this.userMapper = userMapper;
        this.ratingMapper = ratingMapper;
    }

    public Mono<PipelineContext> execute(PipelineContext ctx) {
        Long userId = (Long) ctx.userFeatures().get("userId");
        if (userId == null) return Mono.just(ctx);

        return Mono.zip(redisRepo.getUserProfile(userId), redisRepo.getUserHistory(userId, 100))
            .flatMap(tuple -> {
                Map<String, String> profile = tuple.getT1();
                List<Long> history = tuple.getT2();
                Map<String, Object> enriched = new HashMap<>();
                profile.forEach((k, v) -> {
                    if ("preferredGenres".equals(k) && v != null && !v.isEmpty()) {
                        enriched.put(k, java.util.Arrays.asList(v.split(",")));
                    } else {
                        enriched.put(k, v);
                    }
                });
                if (!history.isEmpty()) enriched.put("histMovieIds", history);
                // DB fallback
                if (profile.isEmpty()) {
                    var user = userMapper.findActiveById(userId);
                    if (user != null) {
                        if (user.getGender() != null) enriched.put("gender", user.getGender());
                        if (user.getAge() != null) enriched.put("age", user.getAge());
                        if (user.getOccupation() != null) enriched.put("occupation", user.getOccupation());
                        if (user.getZipCode() != null) enriched.put("zipCode", user.getZipCode());
                        if (user.getPreferredGenres() != null && user.getPreferredGenres().length > 0) {
                            enriched.put("preferredGenres", java.util.Arrays.asList(user.getPreferredGenres()));
                        }
                    }
                }
                // Add user behavioural statistics for ranking model
                Map<String, Object> userStats = ratingMapper.selectStatsByUser(userId);
                if (userStats != null && !userStats.isEmpty()) {
                    Number avgRating = (Number) userStats.get("avg_rating");
                    Number ratingCount = (Number) userStats.get("rating_count");
                    Number maxTs = (Number) userStats.get("max_ts");
                    Number minTs = (Number) userStats.get("min_ts");

                    if (avgRating != null) {
                        enriched.put("userAvgRating", avgRating.doubleValue());
                    }
                    if (ratingCount != null) {
                        enriched.put("userRatingCount", ratingCount.intValue());
                    }
                    if (maxTs != null && minTs != null) {
                        long activeDays = (maxTs.longValue() - minTs.longValue()) / 86400;
                        enriched.put("userActiveDays", (int) activeDays);
                    }
                }

                PipelineContext enrichedCtx = ctx.withUserFeatures(enriched);
                if (!history.isEmpty()) {
                    enrichedCtx = enrichedCtx.withHistMovieIds(history);
                } else {
                    @SuppressWarnings("unchecked")
                    var reqHist = (List<Long>) ctx.userFeatures().get("histMovieIds");
                    if (reqHist != null && !reqHist.isEmpty()) {
                        enrichedCtx = enrichedCtx.withHistMovieIds(reqHist);
                    }
                }
                return Mono.just(enrichedCtx);
            });
    }
}
