package com.rec.api.handler;

import com.rec.common.model.request.UserFeaturesRequest;
import com.rec.common.model.response.RecommendationItemResponse;
import com.rec.common.model.response.RecommendationResponse;
import com.rec.pipeline.RecommendationPipeline;
import com.rec.repository.mapper.MovieMapper;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.server.ServerRequest;
import org.springframework.web.reactive.function.server.ServerResponse;
import reactor.core.publisher.Mono;

import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Component
public class RecommendationHandler {

    private final RecommendationPipeline pipeline;
    private final MovieMapper movieMapper;

    public RecommendationHandler(RecommendationPipeline pipeline, MovieMapper movieMapper) {
        this.pipeline = pipeline;
        this.movieMapper = movieMapper;
    }

    public Mono<ServerResponse> recommend(ServerRequest request) {
        return request.bodyToMono(UserFeaturesRequest.class)
            .flatMap(req -> {
                Map<String, Object> features = new HashMap<>();
                if (req.userId() != null) features.put("userId", req.userId());
                if (req.gender() != null) features.put("gender", req.gender());
                if (req.age() != null) features.put("age", req.age());
                if (req.occupation() != null) features.put("occupation", req.occupation());
                if (req.zipCode() != null) features.put("zipCode", req.zipCode());
                if (req.histMovieIds() != null) features.put("histMovieIds", req.histMovieIds());
                if (req.preferredGenres() != null) features.put("preferredGenres", req.preferredGenres());
                return pipeline.recommend(features);
            })
            .flatMap(ctx -> {
                var items = ctx.rerankedItems().stream()
                    .map(item -> {
                        var movie = movieMapper.selectById(item.movieId());
                        return new RecommendationItemResponse(item.movieId(),
                            movie != null ? movie.getTitle() : "",
                            movie != null && movie.getGenres() != null ? Arrays.asList(movie.getGenres()) : List.of(),
                            item.score(), null, item.recallType(), null);
                    })
                    .collect(Collectors.toList());
                return ServerResponse.ok().bodyValue(new RecommendationResponse(items, items.size(), "deepfm"));
            });
    }

    public Mono<ServerResponse> health(ServerRequest request) {
        return ServerResponse.ok().bodyValue(Map.of("status", "healthy"));
    }
}
