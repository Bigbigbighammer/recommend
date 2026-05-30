package com.rec.pipeline;

import com.rec.repository.mapper.UserMapper;
import com.rec.repository.redis.UserProfileRedisRepository;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;
import java.util.*;

@Component
public class UserFeatureEnrichmentStage {
    private final UserProfileRedisRepository redisRepo;
    private final UserMapper userMapper;

    public UserFeatureEnrichmentStage(UserProfileRedisRepository redisRepo, UserMapper userMapper) {
        this.redisRepo = redisRepo;
        this.userMapper = userMapper;
    }

    public Mono<PipelineContext> execute(PipelineContext ctx) {
        Long userId = (Long) ctx.userFeatures().get("userId");
        if (userId == null) return Mono.just(ctx);

        return Mono.zip(redisRepo.getUserProfile(userId), redisRepo.getUserHistory(userId, 100))
            .flatMap(tuple -> {
                Map<String, String> profile = tuple.getT1();
                List<Long> history = tuple.getT2();
                Map<String, Object> enriched = new HashMap<>();
                profile.forEach((k, v) -> enriched.put(k, v));
                if (!history.isEmpty()) enriched.put("histMovieIds", history);
                // DB fallback
                if (profile.isEmpty()) {
                    var user = userMapper.findActiveById(userId);
                    if (user != null) {
                        if (user.getGender() != null) enriched.put("gender", user.getGender());
                        if (user.getAge() != null) enriched.put("age", user.getAge());
                        if (user.getOccupation() != null) enriched.put("occupation", user.getOccupation());
                        if (user.getZipCode() != null) enriched.put("zipCode", user.getZipCode());
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
