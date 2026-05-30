package com.funrec.common.model.pipeline;

import java.util.List;

public record RankedItem(
    long movieId, double score, double recallScore, String recallType,
    List<String> genres, int year
) {}
