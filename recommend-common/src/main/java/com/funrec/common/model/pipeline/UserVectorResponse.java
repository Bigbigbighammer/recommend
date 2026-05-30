package com.funrec.common.model.pipeline;

import java.util.List;

public record UserVectorResponse(List<Double> userVector, String version) {}
