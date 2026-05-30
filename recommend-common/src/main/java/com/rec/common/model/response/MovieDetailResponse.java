package com.rec.common.model.response;

import java.util.List;

public record MovieDetailResponse(
    Long movieId,
    String imdbId,
    String title,
    Integer year,
    List<String> genres,
    String description,
    Double avgRating,
    Integer ratingCount,
    Double imdbRating,
    Integer imdbVotes,
    Integer runtimeMinutes,
    String titleType
) {}
