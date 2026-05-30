package com.rec.rpc;

import com.rec.common.exception.InferenceException;
import com.rec.common.model.pipeline.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.time.Duration;
import java.util.List;

@Component
@ConditionalOnProperty(name = "recommend.rpc.client", havingValue = "http", matchIfMissing = true)
public class HttpModelInferenceClient implements ModelInferenceClient {

    private final WebClient webClient;

    public HttpModelInferenceClient(@Value("${recommend.rpc.inference.base-url}") String baseUrl) {
        this.webClient = WebClient.builder()
            .baseUrl(baseUrl)
            .defaultHeaders(h -> h.setContentType(MediaType.APPLICATION_JSON))
            .build();
    }

    @Override
    public Mono<List<CTRPrediction>> predictCTR(RankingRequest request) {
        return webClient.post()
            .uri("/api/predict/ranking")
            .bodyValue(request)
            .retrieve()
            .onStatus(s -> s.is5xxServerError(),
                r -> r.bodyToMono(String.class)
                    .flatMap(msg -> Mono.error(new InferenceException("Model service error: " + msg))))
            .bodyToMono(new ParameterizedTypeReference<List<CTRPrediction>>() {})
            .timeout(Duration.ofMillis(2000));
    }

    @Override
    public Mono<UserVectorResponse> generateUserVector(RecallRequest request) {
        return webClient.post()
            .uri("/api/predict/recall")
            .bodyValue(request)
            .retrieve()
            .onStatus(s -> s.is5xxServerError(),
                r -> r.bodyToMono(String.class)
                    .flatMap(msg -> Mono.error(new InferenceException("Model service error: " + msg))))
            .bodyToMono(UserVectorResponse.class)
            .timeout(Duration.ofMillis(2000));
    }

    @Override
    public Mono<Boolean> health() {
        return webClient.get()
            .uri("/api/health")
            .retrieve()
            .bodyToMono(String.class)
            .map(r -> r.contains("healthy"))
            .onErrorReturn(false);
    }

    @Override
    public Mono<ModelVersion> getVersion(String modelType) {
        return webClient.get()
            .uri("/api/version/" + modelType)
            .retrieve()
            .bodyToMono(ModelVersion.class);
    }
}
