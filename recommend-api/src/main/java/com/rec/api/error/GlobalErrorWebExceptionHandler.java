package com.rec.api.error;

import com.rec.common.exception.AuthException;
import com.rec.common.exception.DataAccessException;
import com.rec.common.exception.InferenceException;
import com.rec.common.exception.RecommendationException;
import org.springframework.boot.autoconfigure.web.WebProperties;
import org.springframework.boot.autoconfigure.web.reactive.error.AbstractErrorWebExceptionHandler;
import org.springframework.boot.web.reactive.error.ErrorAttributes;
import org.springframework.context.ApplicationContext;
import org.springframework.core.annotation.Order;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.codec.ServerCodecConfigurer;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.BodyInserters;
import org.springframework.web.reactive.function.server.RequestPredicates;
import org.springframework.web.reactive.function.server.RouterFunction;
import org.springframework.web.reactive.function.server.RouterFunctions;
import org.springframework.web.reactive.function.server.ServerRequest;
import org.springframework.web.reactive.function.server.ServerResponse;
import reactor.core.publisher.Mono;

import java.util.Map;
import java.util.UUID;

@Component
@Order(-2)
public class GlobalErrorWebExceptionHandler extends AbstractErrorWebExceptionHandler {

    public GlobalErrorWebExceptionHandler(ErrorAttributes errorAttributes,
                                           WebProperties webProperties,
                                           ApplicationContext context,
                                           ServerCodecConfigurer codecConfigurer) {
        super(errorAttributes, webProperties.getResources(), context);
        setMessageWriters(codecConfigurer.getWriters());
    }

    @Override
    protected RouterFunction<ServerResponse> getRoutingFunction(ErrorAttributes errorAttributes) {
        return RouterFunctions.route(RequestPredicates.all(), this::renderErrorResponse);
    }

    private Mono<ServerResponse> renderErrorResponse(ServerRequest request) {
        Throwable error = getError(request);
        HttpStatus status;
        String code;

        if (error instanceof InferenceException) {
            status = HttpStatus.SERVICE_UNAVAILABLE;
            code = "INFERENCE_ERROR";
        } else if (error instanceof RecommendationException) {
            status = HttpStatus.INTERNAL_SERVER_ERROR;
            code = "RECOMMEND_ERROR";
        } else if (error instanceof AuthException) {
            status = HttpStatus.UNAUTHORIZED;
            code = "AUTH_ERROR";
        } else if (error instanceof DataAccessException) {
            status = HttpStatus.INTERNAL_SERVER_ERROR;
            code = "DATA_ERROR";
        } else {
            status = HttpStatus.INTERNAL_SERVER_ERROR;
            code = "INTERNAL_ERROR";
        }

        var body = Map.of("code", code,
            "message", error.getMessage() != null ? error.getMessage() : "Unexpected error",
            "traceId", UUID.randomUUID().toString());

        return ServerResponse.status(status).contentType(MediaType.APPLICATION_JSON)
            .body(BodyInserters.fromValue(body));
    }
}
