package com.rec.api.handler;

import com.rec.common.model.request.RatingCreateRequest;
import com.rec.common.model.response.RatingResponse;
import com.rec.common.model.response.UserRatingResponse;
import com.rec.repository.entity.RatingEntity;
import com.rec.repository.mapper.MovieMapper;
import com.rec.repository.mapper.RatingMapper;
import com.rec.repository.redis.UserProfileRedisRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.server.ServerRequest;
import org.springframework.web.reactive.function.server.ServerResponse;
import reactor.core.publisher.Mono;

import java.util.Map;

@Component
public class RatingHandler {

    private static final Logger log = LoggerFactory.getLogger(RatingHandler.class);

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
        Long userId = AuthUtil.extractUserId(request);
        return request.bodyToMono(RatingCreateRequest.class)
            .flatMap(req -> {
                var existing = ratingMapper.findByUserAndMovie(userId, req.movieId());
                var rating = new RatingEntity();
                rating.setUserId(userId);
                rating.setMovieId(req.movieId());
                rating.setRating(req.rating());
                rating.setTimestamp(System.currentTimeMillis());

                int oldRating = 0;
                if (existing != null) {
                    oldRating = existing.getRating();
                    ratingMapper.deleteByUserAndMovie(userId, req.movieId());
                }
                ratingMapper.insert(rating);
                updateMovieAvgRating(req.movieId());

                var ops = redisRepo.pushUserHistory(userId, req.movieId())
                    .then(redisRepo.updateUserProfile(userId, Map.of()));

                if (existing != null && oldRating != req.rating()) {
                    // rating changed: adjust UCB reward delta
                    int delta = req.rating() - oldRating;
                    ops = ops.then(redisRepo.updateUCBStatsDelta(userId,
                        getMovieGenre(req.movieId()), delta));
                } else if (existing == null) {
                    ops = ops.then(redisRepo.updateUCBStats(userId,
                        getMovieGenre(req.movieId()), req.rating()));
                }

                String title = getMovieTitle(req.movieId());
                return ops.then(ServerResponse.ok().bodyValue(
                    new RatingResponse(userId, req.movieId(), title, req.rating(), rating.getTimestamp())));
            });
    }

    public Mono<ServerResponse> getMovieRating(ServerRequest request) {
        Long userId = AuthUtil.extractUserId(request);
        Long movieId = Long.parseLong(request.pathVariable("id"));
        var rating = ratingMapper.findByUserAndMovie(userId, movieId);
        return ServerResponse.ok().bodyValue(rating != null
            ? new UserRatingResponse(rating.getRating(), true)
            : new UserRatingResponse(null, false));
    }

    public Mono<ServerResponse> deleteRating(ServerRequest request) {
        Long userId = AuthUtil.extractUserId(request);
        Long movieId = Long.parseLong(request.pathVariable("id"));

        var existing = ratingMapper.findByUserAndMovie(userId, movieId);
        if (existing == null) {
            return ServerResponse.notFound().build();
        }

        ratingMapper.deleteByUserAndMovie(userId, movieId);
        updateMovieAvgRating(movieId);

        return redisRepo.removeUserHistory(userId, movieId)
            .then(redisRepo.decrementUCBStats(userId,
                getMovieGenre(movieId), existing.getRating()))
            .then(ServerResponse.noContent().build());
    }

    private void updateMovieAvgRating(Long movieId) {
        var movie = movieMapper.selectById(movieId);
        if (movie == null) return;

        Double avg = ratingMapper.avgRatingByMovie(movieId);
        int count = ratingMapper.countByMovie(movieId);

        movie.setAvgRating(avg);
        movie.setRatingCount(count);
        movieMapper.updateById(movie);
    }

    private String getMovieGenre(Long movieId) {
        var movie = movieMapper.selectById(movieId);
        return (movie != null && movie.getGenres() != null && movie.getGenres().length > 0)
            ? movie.getGenres()[0] : "Unknown";
    }

    private String getMovieTitle(Long movieId) {
        var movie = movieMapper.selectById(movieId);
        return movie != null ? movie.getTitle() : "";
    }
}
