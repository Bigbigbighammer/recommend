package com.funrec.api.handler;

import com.funrec.common.model.response.PersonDetailResponse;
import com.funrec.repository.mapper.NameBasicsMapper;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.server.ServerRequest;
import org.springframework.web.reactive.function.server.ServerResponse;
import reactor.core.publisher.Mono;

import java.util.Arrays;
import java.util.List;

@Component
public class PeopleHandler {

    private final NameBasicsMapper nameBasicsMapper;

    public PeopleHandler(NameBasicsMapper nameBasicsMapper) {
        this.nameBasicsMapper = nameBasicsMapper;
    }

    public Mono<ServerResponse> detail(ServerRequest request) {
        String id = request.pathVariable("id");
        var p = nameBasicsMapper.findByNconst(id);
        if (p == null) return ServerResponse.notFound().build();
        return ServerResponse.ok().bodyValue(new PersonDetailResponse(p.getNconst(), p.getPrimaryName(),
            p.getBirthYear(), p.getDeathYear(),
            p.getPrimaryProfession() != null ? Arrays.asList(p.getPrimaryProfession()) : List.of(),
            p.getKnownForTitles() != null ? Arrays.asList(p.getKnownForTitles()) : List.of()));
    }
}
