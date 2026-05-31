package com.rec.api.handler;

import com.rec.common.model.request.UserUpdateRequest;
import com.rec.common.model.response.RatingResponse;
import com.rec.common.model.response.UserProfileResponse;
import com.rec.repository.mapper.RatingMapper;
import com.rec.repository.mapper.UserMapper;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.server.ServerRequest;
import org.springframework.web.reactive.function.server.ServerResponse;
import reactor.core.publisher.Mono;

import java.util.Arrays;
import java.util.List;
import java.util.stream.Collectors;

@Component
public class UserHandler {

    private final UserMapper userMapper;
    private final RatingMapper ratingMapper;

    public UserHandler(UserMapper userMapper, RatingMapper ratingMapper) {
        this.userMapper = userMapper;
        this.ratingMapper = ratingMapper;
    }

    public Mono<ServerResponse> getProfile(ServerRequest request) {
        Long userId = extractUserId(request);
        var user = userMapper.findActiveById(userId);
        if (user == null) return ServerResponse.notFound().build();

        List<RatingResponse> recentRatings = ratingMapper.findRecentByUser(userId, 10)
            .stream().map(r -> new RatingResponse(r.getUserId(), r.getMovieId(), r.getTitle(), r.getRating(), r.getTimestamp()))
            .collect(Collectors.toList());

        var profile = new UserProfileResponse(user.getUserId(), user.getEmail(), user.getUsername(),
            user.getGender(), user.getAge(), user.getOccupation(), user.getZipCode(),
            user.getIsSuperuser() == 1, user.getCreatedAt(),
            user.getPreferredGenres() != null ? Arrays.asList(user.getPreferredGenres()) : List.of(),
            List.of(), recentRatings);

        return ServerResponse.ok().bodyValue(profile);
    }

    public Mono<ServerResponse> updateProfile(ServerRequest request) {
        Long userId = extractUserId(request);
        return request.bodyToMono(UserUpdateRequest.class)
            .flatMap(req -> {
                var user = userMapper.findActiveById(userId);
                if (user == null) return ServerResponse.notFound().build();
                if (req.gender() != null) user.setGender(req.gender());
                if (req.age() != null) user.setAge(req.age());
                if (req.occupation() != null) user.setOccupation(req.occupation());
                if (req.zipCode() != null) user.setZipCode(req.zipCode());
                if (req.preferredGenres() != null) user.setPreferredGenres(req.preferredGenres().toArray(String[]::new));
                userMapper.updateById(user);
                return ServerResponse.ok().build();
            });
    }

    private Long extractUserId(ServerRequest request) {
        return AuthUtil.extractUserId(request);
    }
}
