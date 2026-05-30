package com.funrec.common.model.pipeline;

import java.util.List;

public record ItemFeatures(String genre, List<String> genresList, int isAdult, int year) {}
