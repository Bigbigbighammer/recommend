package com.rec.api.handler;

import com.rec.common.model.response.MovieListItem;
import com.rec.repository.es.MovieSearchRepository;
import com.rec.repository.mapper.MovieMapper;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.server.ServerRequest;
import org.springframework.web.reactive.function.server.ServerResponse;
import reactor.core.publisher.Mono;

import java.util.*;
import java.util.stream.Collectors;

@Component
public class SearchHandler {

    private final MovieSearchRepository esRepo;
    private final MovieMapper movieMapper;

    public SearchHandler(MovieSearchRepository esRepo, MovieMapper movieMapper) {
        this.esRepo = esRepo;
        this.movieMapper = movieMapper;
    }

    public Mono<ServerResponse> searchMovies(ServerRequest request) {
        String q = request.queryParam("q").orElse("");
        int from = Integer.parseInt(request.queryParam("from").orElse("0"));
        int size = Integer.parseInt(request.queryParam("size").orElse("20"));
        return esRepo.searchByKeyword(q, from, size).collectList()
            .map(results -> {
                List<Long> ids = results.stream().map(r -> r.movieId()).toList();
                Map<Long, String> posterMap = ids.isEmpty() ? Map.of()
                    : movieMapper.selectBatchIds(ids).stream()
                        .filter(m -> m.getPosterUrl() != null)
                        .collect(Collectors.toMap(m -> m.getMovieId(), m -> m.getPosterUrl()));
                return results.stream()
                    .map(r -> new MovieListItem(r.movieId(), r.title(), r.year(), r.genres(),
                        r.avgRating(), r.imdbRating(), posterMap.get(r.movieId())))
                    .collect(Collectors.toList());
            })
            .flatMap(items -> ServerResponse.ok().bodyValue(items));
    }

    public Mono<ServerResponse> suggest(ServerRequest request) {
        String q = request.queryParam("q").orElse("");
        return esRepo.suggest(q, 10).collectList()
            .flatMap(results -> ServerResponse.ok().bodyValue(results));
    }
}
