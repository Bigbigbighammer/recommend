package com.funrec.api.handler;

import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.server.ServerRequest;
import org.springframework.web.reactive.function.server.ServerResponse;
import reactor.core.publisher.Mono;

import java.util.Map;

@Component
public class HealthHandler {

    public Mono<ServerResponse> check(ServerRequest request) {
        return ServerResponse.ok().bodyValue(Map.of("status", "healthy", "version", "1.0.0"));
    }
}
