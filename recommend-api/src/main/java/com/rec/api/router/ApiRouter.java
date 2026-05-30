package com.rec.api.router;

import com.rec.api.handler.AuthHandler;
import com.rec.api.handler.GenreHandler;
import com.rec.api.handler.HealthHandler;
import com.rec.api.handler.MovieHandler;
import com.rec.api.handler.PeopleHandler;
import com.rec.api.handler.RatingHandler;
import com.rec.api.handler.RecommendationHandler;
import com.rec.api.handler.SearchHandler;
import com.rec.api.handler.StatsHandler;
import com.rec.api.handler.UserHandler;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.reactive.function.server.RouterFunction;
import org.springframework.web.reactive.function.server.RouterFunctions;
import org.springframework.web.reactive.function.server.ServerResponse;

import static org.springframework.web.reactive.function.server.RequestPredicates.DELETE;
import static org.springframework.web.reactive.function.server.RequestPredicates.GET;
import static org.springframework.web.reactive.function.server.RequestPredicates.POST;
import static org.springframework.web.reactive.function.server.RequestPredicates.PUT;

@Configuration
public class ApiRouter {

    @Bean
    public RouterFunction<ServerResponse> routes(
        AuthHandler authHandler, UserHandler userHandler, MovieHandler movieHandler,
        RatingHandler ratingHandler, RecommendationHandler recommendationHandler,
        SearchHandler searchHandler, GenreHandler genreHandler,
        PeopleHandler peopleHandler, StatsHandler statsHandler, HealthHandler healthHandler) {
        return RouterFunctions.route()
            .GET("/health", healthHandler::check)
            .POST("/api/auth/signup", authHandler::signup)
            .POST("/api/auth/login", authHandler::login)
            .GET("/api/users/me", userHandler::getProfile)
            .PUT("/api/users/me", userHandler::updateProfile)
            .POST("/api/movies", movieHandler::create)
            .GET("/api/movies", movieHandler::list)
            .GET("/api/movies/popular", movieHandler::popular)
            .GET("/api/movies/{id}", movieHandler::detail)
            .GET("/api/movies/{id}/cast", movieHandler::cast)
            .GET("/api/movies/{id}/crew", movieHandler::crew)
            .POST("/api/ratings", ratingHandler::createRating)
            .GET("/api/ratings/movie/{id}", ratingHandler::getMovieRating)
            .DELETE("/api/ratings/movie/{id}", ratingHandler::deleteRating)
            .POST("/api/recommendations/recommend", recommendationHandler::recommend)
            .GET("/api/recommendations/health", recommendationHandler::health)
            .GET("/api/search/movies", searchHandler::searchMovies)
            .GET("/api/search/suggest", searchHandler::suggest)
            .GET("/api/genres", genreHandler::list)
            .GET("/api/people/{id}", peopleHandler::detail)
            .GET("/api/stats", statsHandler::dashboard)
            .build();
    }
}
