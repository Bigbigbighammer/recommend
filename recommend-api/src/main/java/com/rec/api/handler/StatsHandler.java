package com.rec.api.handler;

import com.rec.repository.mapper.MovieMapper;
import com.rec.repository.mapper.RatingMapper;
import com.rec.repository.mapper.UserMapper;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.server.ServerRequest;
import org.springframework.web.reactive.function.server.ServerResponse;
import reactor.core.publisher.Mono;

import java.util.Map;

@Component
public class StatsHandler {

    private final MovieMapper movieMapper;
    private final UserMapper userMapper;
    private final RatingMapper ratingMapper;

    public StatsHandler(MovieMapper movieMapper, UserMapper userMapper, RatingMapper ratingMapper) {
        this.movieMapper = movieMapper;
        this.userMapper = userMapper;
        this.ratingMapper = ratingMapper;
    }

    public Mono<ServerResponse> dashboard(ServerRequest request) {
        return ServerResponse.ok().bodyValue(Map.of(
            "total_movies", (Object) movieMapper.selectCount(null),
            "total_users", userMapper.selectCount(null),
            "total_ratings", ratingMapper.selectCount(null)));
    }
}
