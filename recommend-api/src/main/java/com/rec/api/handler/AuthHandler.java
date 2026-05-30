package com.rec.api.handler;

import com.rec.common.model.request.LoginRequest;
import com.rec.common.model.request.SignupRequest;
import com.rec.common.model.response.TokenResponse;
import com.rec.repository.entity.UserEntity;
import com.rec.repository.mapper.UserMapper;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.server.ServerRequest;
import org.springframework.web.reactive.function.server.ServerResponse;
import reactor.core.publisher.Mono;

@Component
public class AuthHandler {

    private final UserMapper userMapper;

    public AuthHandler(UserMapper userMapper) {
        this.userMapper = userMapper;
    }

    public Mono<ServerResponse> signup(ServerRequest request) {
        return request.bodyToMono(SignupRequest.class)
            .flatMap(req -> {
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
                return ServerResponse.ok().bodyValue(new TokenResponse("jwt-placeholder"));
            });
    }

    public Mono<ServerResponse> login(ServerRequest request) {
        return request.bodyToMono(LoginRequest.class)
            .flatMap(req -> {
                var user = userMapper.findByEmail(req.email());
                if (user == null) {
                    return ServerResponse.badRequest().bodyValue("Invalid credentials");
                }
                return ServerResponse.ok().bodyValue(new TokenResponse("jwt-placeholder"));
            });
    }
}
