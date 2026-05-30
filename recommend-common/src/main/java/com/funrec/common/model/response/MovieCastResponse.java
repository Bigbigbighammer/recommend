package com.funrec.common.model.response;

import java.util.List;

public record MovieCastResponse(
    Long movieId,
    String movieTitle,
    List<CastMemberResponse> cast
) {}
