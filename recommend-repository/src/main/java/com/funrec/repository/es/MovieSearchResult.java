package com.funrec.repository.es;

import java.util.List;

public record MovieSearchResult(
    Long movieId,
    String title,
    Integer year,
    List<String> genres,
    Double avgRating,
    Integer ratingCount,
    Double imdbRating,
    Integer imdbVotes,
    String description
) {}
