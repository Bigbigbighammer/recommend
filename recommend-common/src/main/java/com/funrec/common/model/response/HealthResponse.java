package com.funrec.common.model.response;

public record HealthResponse(
    String status,
    String version,
    String database,
    String redis,
    String elasticsearch
) {}
