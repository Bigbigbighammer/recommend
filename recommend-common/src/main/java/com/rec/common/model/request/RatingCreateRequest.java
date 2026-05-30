package com.rec.common.model.request;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;

public record RatingCreateRequest(
    @NotNull Long movieId,
    @NotNull @Min(1) @Max(10) Integer rating
) {}
