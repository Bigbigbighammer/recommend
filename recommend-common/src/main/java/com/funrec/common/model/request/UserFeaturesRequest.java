package com.funrec.common.model.request;

import java.util.List;

public record UserFeaturesRequest(
    Long userId,
    String gender,
    String age,
    String occupation,
    String zipCode,
    List<Long> histMovieIds,
    List<String> preferredGenres
) {}
