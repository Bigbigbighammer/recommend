package com.rec.rpc;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.rec.common.exception.InferenceException;
import com.rec.common.model.pipeline.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.time.Duration;
import java.util.List;

@Component
@ConditionalOnProperty(name = "recommend.rpc.client", havingValue = "http", matchIfMissing = true)
public class HttpModelInferenceClient implements ModelInferenceClient {

    private static final Logger log = LoggerFactory.getLogger(HttpModelInferenceClient.class);

    private final WebClient webClient;
    private final ObjectMapper objectMapper;

    public HttpModelInferenceClient(@Value("${recommend.rpc.inference.base-url}") String baseUrl) {
        this.objectMapper = new ObjectMapper()
            .setPropertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE);
        this.webClient = WebClient.builder()
            .baseUrl(baseUrl)
            .build();
    }

    @Override
    public Mono<List<CTRPrediction>> predictCTR(RankingRequest request) {
        return sendRequest("/api/predict/ranking", request)
            .flatMap(body -> {
                try {
                    CTRPrediction[] arr = objectMapper.readValue(body, CTRPrediction[].class);
                    return Mono.just(List.of(arr));
                } catch (Exception e) {
                    return Mono.error(new InferenceException("Failed to parse ranking response: " + e.getMessage()));
                }
            });
    }

    @Override
    public Mono<UserVectorResponse> generateUserVector(RecallRequest request) {
        return sendRequest("/api/predict/recall", request)
            .flatMap(body -> {
                try {
                    return Mono.just(objectMapper.readValue(body, UserVectorResponse.class));
                } catch (Exception e) {
                    return Mono.error(new InferenceException("Failed to parse recall response: " + e.getMessage()));
                }
            });
    }

    private Mono<String> sendRequest(String uri, Object request) {
        String json;
        try {
            json = objectMapper.writeValueAsString(request);
            log.debug("RPC request to {}: {}", uri, json);
        } catch (Exception e) {
            return Mono.error(new InferenceException("Failed to serialize request: " + e.getMessage()));
        }
        return webClient.post()
            .uri(uri)
            .contentType(MediaType.APPLICATION_JSON)
            .bodyValue(json)
            .retrieve()
            .onStatus(s -> s.is5xxServerError(),
                r -> r.bodyToMono(String.class)
                    .flatMap(msg -> Mono.error(new InferenceException("Model service error: " + msg))))
            .bodyToMono(String.class)
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
            .bodyToMono(String.class)
            .flatMap(body -> {
                try {
                    return Mono.just(objectMapper.readValue(body, ModelVersion.class));
                } catch (Exception e) {
                    return Mono.error(new InferenceException("Failed to parse version: " + e.getMessage()));
                }
            });
    }
}
