package com.rec.api.handler;

import com.rec.common.exception.AuthException;
import com.rec.common.model.request.LoginRequest;
import com.rec.common.model.request.SignupRequest;
import com.rec.common.model.response.TokenResponse;
import com.rec.repository.entity.UserEntity;
import com.rec.repository.mapper.UserMapper;
import com.rec.repository.redis.UserProfileRedisRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.server.ServerRequest;
import org.springframework.web.reactive.function.server.ServerResponse;
import reactor.core.publisher.Mono;

import java.util.HashMap;
import java.util.Map;

@Component
public class AuthHandler {

    private static final Logger log = LoggerFactory.getLogger(AuthHandler.class);

    private final UserMapper userMapper;
    private final UserProfileRedisRepository redisRepo;

    public AuthHandler(UserMapper userMapper, UserProfileRedisRepository redisRepo) {
        this.userMapper = userMapper;
        this.redisRepo = redisRepo;
    }

    public Mono<ServerResponse> signup(ServerRequest request) {
        return request.bodyToMono(SignupRequest.class)
            .flatMap(req -> {
                if (req.email() == null || req.email().isBlank()) {
                    return Mono.error(new AuthException("Email is required"));
                }
                if (req.password() == null || req.password().length() < 6) {
                    return Mono.error(new AuthException("Password must be at least 6 characters"));
                }
                var existing = userMapper.findByEmail(req.email());
                if (existing != null) {
                    return Mono.error(new AuthException("An account with this email already exists"));
                }
                var user = new UserEntity();
                user.setEmail(req.email());
                user.setUsername(req.email().split("@")[0]);
                user.setHashedPassword(req.password());
                user.setGender(req.gender());
                user.setAge(req.age());
                user.setOccupation(req.occupation());
                user.setZipCode(req.zipCode());
                user.setPreferredGenres(req.preferredGenres() != null
                    ? req.preferredGenres().toArray(String[]::new) : null);
                user.setIsActive(1);
                user.setIsSuperuser(0);
                userMapper.insert(user);

                Map<String, String> profile = new HashMap<>();
                if (req.gender() != null) profile.put("gender", req.gender());
                if (req.age() != null) profile.put("age", req.age());
                if (req.occupation() != null) profile.put("occupation", req.occupation());
                if (req.zipCode() != null) profile.put("zipCode", req.zipCode());
                if (req.preferredGenres() != null && !req.preferredGenres().isEmpty())
                    profile.put("preferredGenres", String.join(",", req.preferredGenres()));
                return redisRepo.updateUserProfile(user.getUserId(), profile)
                    .then(ServerResponse.ok().bodyValue(new TokenResponse(AuthUtil.encodeToken(user.getUserId()))));
            });
    }

    public Mono<ServerResponse> login(ServerRequest request) {
        return request.bodyToMono(LoginRequest.class)
            .flatMap(req -> {
                if (req.email() == null || req.email().isBlank()) {
                    return Mono.error(new AuthException("Email is required"));
                }
                var user = userMapper.findByEmail(req.email());
                if (user == null) {
                    return Mono.error(new AuthException("Invalid email or password"));
                }
                if (!req.password().equals(user.getHashedPassword())) {
                    return Mono.error(new AuthException("Invalid email or password"));
                }
                return ServerResponse.ok().bodyValue(new TokenResponse(AuthUtil.encodeToken(user.getUserId())));
            });
    }
}
