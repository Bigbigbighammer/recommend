package com.rec.api.handler;

import com.rec.common.model.request.RatingCreateRequest;
import com.rec.common.model.response.RatingResponse;
import com.rec.common.model.response.UserRatingResponse;
import com.rec.repository.entity.RatingEntity;
import com.rec.repository.mapper.MovieMapper;
import com.rec.repository.mapper.RatingMapper;
import com.rec.repository.redis.UserProfileRedisRepository;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.server.ServerRequest;
import org.springframework.web.reactive.function.server.ServerResponse;
import reactor.core.publisher.Mono;

import java.util.Map;

@Component
public class RatingHandler {

    private final RatingMapper ratingMapper;
    private final MovieMapper movieMapper;
    private final UserProfileRedisRepository redisRepo;

    public RatingHandler(RatingMapper ratingMapper, MovieMapper movieMapper,
                         UserProfileRedisRepository redisRepo) {
        this.ratingMapper = ratingMapper;
        this.movieMapper = movieMapper;
        this.redisRepo = redisRepo;
    }

    public Mono<ServerResponse> createRating(ServerRequest request) {
        Long userId = extractUserId(request);
        return request.bodyToMono(RatingCreateRequest.class)
            .flatMap(req -> {
                var rating = new RatingEntity();
                rating.setUserId(userId);
                rating.setMovieId(req.movieId());
                rating.setRating(req.rating());
                rating.setTimestamp(System.currentTimeMillis());
                ratingMapper.insert(rating);                                     // 1. PG
                updateMovieAvgRating(req.movieId());                             // 1. PG

                return redisRepo.pushUserHistory(userId, req.movieId())          // 3. Redis history
                    .then(redisRepo.updateUserProfile(userId, Map.of()))         // 4. Redis profile
                    .then(redisRepo.updateUCBStats(userId,                       // 5. Redis UCB
                        getMovieGenre(req.movieId()), req.rating()))
                    .then(ServerResponse.ok().bodyValue(
                        new RatingResponse(userId, req.movieId(), req.rating(), rating.getTimestamp())));
            });
    }

    public Mono<ServerResponse> getMovieRating(ServerRequest request) {
        Long userId = extractUserId(request);
        Long movieId = Long.parseLong(request.pathVariable("id"));
        var rating = ratingMapper.findByUserAndMovie(userId, movieId);
        return ServerResponse.ok().bodyValue(rating != null
            ? new UserRatingResponse(rating.getRating(), true)
            : new UserRatingResponse(null, false));
    }

    public Mono<ServerResponse> deleteRating(ServerRequest request) {
        Long userId = extractUserId(request);
        Long movieId = Long.parseLong(request.pathVariable("id"));
        ratingMapper.deleteByUserAndMovie(userId, movieId);
        return ServerResponse.noContent().build();
    }

    private void updateMovieAvgRating(Long movieId) {
        var movie = movieMapper.selectById(movieId);
        if (movie != null) {
            movie.setRatingCount((movie.getRatingCount() != null ? movie.getRatingCount() : 0) + 1);
            movieMapper.updateById(movie);
        }
    }

    private String getMovieGenre(Long movieId) {
        var movie = movieMapper.selectById(movieId);
        return (movie != null && movie.getGenres() != null && movie.getGenres().length > 0)
            ? movie.getGenres()[0] : "Unknown";
    }

    private Long extractUserId(ServerRequest request) {
        return 1L; // MVP placeholder
    }
}
