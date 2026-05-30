package com.rec.common.model.request;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Positive;
import java.util.List;

public record MovieCreateRequest(
    @NotBlank String title,
    String imdbId,
    Integer year,
    List<String> genres,
    String description,
    @Positive Integer runtimeMinutes,
    String titleType,
    Double imdbRating,
    Integer imdbVotes
) {}
