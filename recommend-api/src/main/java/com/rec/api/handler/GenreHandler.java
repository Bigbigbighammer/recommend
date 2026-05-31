package com.rec.api.handler;

import com.rec.common.model.response.GenreListResponse;
import com.rec.repository.mapper.GenreMapper;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.server.ServerRequest;
import org.springframework.web.reactive.function.server.ServerResponse;
import reactor.core.publisher.Mono;

import java.util.List;
import java.util.stream.Collectors;

@Component
public class GenreHandler {

    private final GenreMapper genreMapper;

    public GenreHandler(GenreMapper genreMapper) {
        this.genreMapper = genreMapper;
    }

    public Mono<ServerResponse> list(ServerRequest request) {
        List<String> genres = genreMapper.findAllNames().stream()
            .map(GenreHandler::normalize)
            .distinct()
            .sorted()
            .collect(Collectors.toList());
        return Mono.just(new GenreListResponse(genres))
            .flatMap(r -> ServerResponse.ok().bodyValue(r));
    }

    public static String normalize(String genre) {
        return genre.replace("''", "'");
    }
}
