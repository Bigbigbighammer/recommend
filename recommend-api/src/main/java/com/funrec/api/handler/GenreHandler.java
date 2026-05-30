package com.funrec.api.handler;

import com.funrec.common.model.response.GenreListResponse;
import com.funrec.repository.mapper.GenreMapper;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.server.ServerRequest;
import org.springframework.web.reactive.function.server.ServerResponse;
import reactor.core.publisher.Mono;

@Component
public class GenreHandler {

    private final GenreMapper genreMapper;

    public GenreHandler(GenreMapper genreMapper) {
        this.genreMapper = genreMapper;
    }

    public Mono<ServerResponse> list(ServerRequest request) {
        return Mono.just(new GenreListResponse(genreMapper.findAllNames()))
            .flatMap(r -> ServerResponse.ok().bodyValue(r));
    }
}
