package com.rec.common.model.response;

import java.util.List;

public record MovieListResponse(
    List<MovieListItem> items,
    long total,
    int page,
    int pageSize,
    boolean hasNext
) {}
