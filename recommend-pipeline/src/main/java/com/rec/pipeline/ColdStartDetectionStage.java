package com.rec.pipeline;

import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;

@Component
public class ColdStartDetectionStage {
    private static final int COLD_START_THRESHOLD = 5;

    public Mono<PipelineContext> execute(PipelineContext ctx) {
        return Mono.just(ctx.withColdStart(ctx.histMovieIds().size() < COLD_START_THRESHOLD));
    }
}
