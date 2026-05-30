package com.rec.common.model.response;

import com.fasterxml.jackson.annotation.JsonProperty;

public record TokenResponse(
    @JsonProperty("access_token") String accessToken,
    @JsonProperty("token_type") String tokenType
) {
    public TokenResponse(String accessToken) {
        this(accessToken, "bearer");
    }
}
