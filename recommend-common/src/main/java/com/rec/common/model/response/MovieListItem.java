package com.rec.common.model.response;

import java.util.List;

public record MovieListItem(
    Long movieId,
    String title,
    Integer year,
    List<String> genres,
    Double avgRating,
    Double imdbRating,
    String posterUrl
) {}
