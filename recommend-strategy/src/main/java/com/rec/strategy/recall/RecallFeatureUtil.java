package com.rec.strategy.recall;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

final class RecallFeatureUtil {

    private RecallFeatureUtil() {
    }

    static List<Long> history(Map<String, Object> userFeatures) {
        Object value = userFeatures.getOrDefault("histMovieIds", List.of());
        if (!(value instanceof List<?> list)) {
            return List.of();
        }

        List<Long> result = new ArrayList<>(list.size());
        for (Object item : list) {
            Long movieId = toLong(item);
            if (movieId != null) {
                result.add(movieId);
            }
        }
        return result;
    }

    static Long userId(Map<String, Object> userFeatures) {
        return toLong(userFeatures.get("userId"));
    }

    private static Long toLong(Object value) {
        if (value == null) {
            return null;
        }
        if (value instanceof Number number) {
            return number.longValue();
        }
        try {
            String text = value.toString().trim();
            return text.isEmpty() ? null : Long.parseLong(text);
        } catch (NumberFormatException e) {
            return null;
        }
    }
}
