package com.funrec.common.config;

import org.springframework.boot.context.properties.ConfigurationProperties;
import java.util.Map;

@ConfigurationProperties(prefix = "recommend")
public record RecommendProperties(
    Rpc rpc,
    Strategy strategy
) {
    public record Rpc(String client, Inference inference) {
        public record Inference(String baseUrl, int connectTimeout, int readTimeout, int maxRetries) {}
    }

    public record Strategy(
        Map<String, Map<String, Boolean>> recall,
        Map<String, Map<String, Boolean>> ranking,
        Map<String, Map<String, Boolean>> reranking,
        Map<String, Map<String, Boolean>> coldstart
    ) {}
}
