package com.funrec.common.model.response;

import java.time.LocalDateTime;
import java.util.List;

public record UserProfileResponse(
    Long userId,
    String email,
    String username,
    String gender,
    String age,
    String occupation,
    String zipCode,
    Boolean isSuperuser,
    LocalDateTime createdAt,
    List<String> preferredGenres,
    List<String> frequentGenres,
    List<RatingResponse> recentRatings
) {}
