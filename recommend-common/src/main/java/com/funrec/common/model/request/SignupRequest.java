package com.funrec.common.model.request;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import java.util.List;

public record SignupRequest(
    @NotBlank @Email String email,
    @NotBlank @Size(min = 6) String password,
    String gender,
    String age,
    String occupation,
    String zipCode,
    List<String> preferredGenres
) {}
