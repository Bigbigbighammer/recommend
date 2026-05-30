package com.funrec.common.model.response;

import java.util.List;

public record PersonDetailResponse(
    String personId,
    String name,
    Integer birthYear,
    Integer deathYear,
    List<String> professions,
    List<String> knownForTitles
) {}
