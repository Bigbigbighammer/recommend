package com.rec.common.model.request;

import java.util.List;

public record UserUpdateRequest(
    String gender,
    String age,
    String occupation,
    String zipCode,
    List<String> preferredGenres
) {}
