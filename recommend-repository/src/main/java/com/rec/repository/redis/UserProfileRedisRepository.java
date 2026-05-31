package com.rec.repository.redis;

import org.springframework.data.redis.core.ReactiveRedisTemplate;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;

import java.util.*;

@Component
public class UserProfileRedisRepository {

    private final ReactiveRedisTemplate<String, String> redis;

    public UserProfileRedisRepository(ReactiveRedisTemplate<String, String> redis) {
        this.redis = redis;
    }

    // ===== Read =====

    public Mono<Map<String, String>> getUserProfile(Long userId) {
        return redis.<String, String>opsForHash()
            .entries("user:" + userId + ":profile")
            .collectMap(Map.Entry::getKey, e -> String.valueOf(e.getValue()))
            .defaultIfEmpty(Collections.emptyMap());
    }

    public Mono<List<Long>> getUserHistory(Long userId, int maxLen) {
        return redis.opsForList()
            .range("user:" + userId + ":history", 0, maxLen - 1)
            .map(Long::parseLong)
            .collectList();
    }

    public Mono<Map<String, Map<String, Integer>>> getUCBStats(Long userId) {
        return redis.<String, String>opsForHash()
            .entries("user:" + userId + ":genre_ucb")
            .collectMap(Map.Entry::getKey, e -> {
                String[] parts = e.getValue().toString().split(":");
                Map<String, Integer> stat = new HashMap<>();
                stat.put("n", Integer.parseInt(parts[0]));
                stat.put("reward", Integer.parseInt(parts[1]));
                return stat;
            });
    }

    // ===== Write =====

    public Mono<Long> pushUserHistory(Long userId, Long movieId) {
        return redis.opsForList().leftPush("user:" + userId + ":history", movieId.toString());
    }

    public Mono<Void> updateUserProfile(Long userId, Map<String, String> profile) {
        if (profile.isEmpty()) {
            return Mono.empty();
        }
        return redis.opsForHash()
            .putAll("user:" + userId + ":profile", profile)
            .then();
    }

    public Mono<Void> updateUCBStats(Long userId, String genre, int reward) {
        String key = "user:" + userId + ":genre_ucb";
        return redis.opsForHash().increment(key, genre + ":n", 1)
            .then(redis.opsForHash().increment(key, genre + ":reward", reward))
            .then();
    }

    public Mono<Long> removeUserHistory(Long userId, Long movieId) {
        return redis.opsForList().remove("user:" + userId + ":history", 1, movieId.toString());
    }

    public Mono<Void> decrementUCBStats(Long userId, String genre, int reward) {
        String key = "user:" + userId + ":genre_ucb";
        return redis.opsForHash().increment(key, genre + ":n", -1)
            .then(redis.opsForHash().increment(key, genre + ":reward", -reward))
            .then();
    }

    public Mono<Void> updateUCBStatsDelta(Long userId, String genre, int delta) {
        String key = "user:" + userId + ":genre_ucb";
        return redis.opsForHash().increment(key, genre + ":reward", delta)
            .then();
    }
}
