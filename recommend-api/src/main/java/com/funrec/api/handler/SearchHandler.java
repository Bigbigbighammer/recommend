package com.funrec.api.handler;

import com.funrec.repository.es.MovieSearchRepository;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.server.ServerRequest;
import org.springframework.web.reactive.function.server.ServerResponse;
import reactor.core.publisher.Mono;

@Component
public class SearchHandler {

    private final MovieSearchRepository esRepo;

    public SearchHandler(MovieSearchRepository esRepo) {
        this.esRepo = esRepo;
    }

    public Mono<ServerResponse> searchMovies(ServerRequest request) {
        String q = request.queryParam("q").orElse("");
        int from = Integer.parseInt(request.queryParam("from").orElse("0"));
        int size = Integer.parseInt(request.queryParam("size").orElse("20"));
        return esRepo.searchByKeyword(q, from, size).collectList()
            .flatMap(results -> ServerResponse.ok().bodyValue(results));
    }

    public Mono<ServerResponse> suggest(ServerRequest request) {
        String q = request.queryParam("q").orElse("");
        return esRepo.suggest(q, 10).collectList()
            .flatMap(results -> ServerResponse.ok().bodyValue(results));
    }
}
