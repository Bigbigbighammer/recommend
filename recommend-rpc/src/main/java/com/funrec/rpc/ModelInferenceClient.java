package com.funrec.rpc;

import com.funrec.common.model.pipeline.*;
import reactor.core.publisher.Mono;

import java.util.List;

public interface ModelInferenceClient {

    Mono<List<CTRPrediction>> predictCTR(RankingRequest request);

    Mono<UserVectorResponse> generateUserVector(RecallRequest request);

    Mono<Boolean> health();

    Mono<ModelVersion> getVersion(String modelType);
}
