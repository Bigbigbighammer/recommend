package com.rec.api.handler;

import com.rec.common.exception.AuthException;
import org.springframework.web.reactive.function.server.ServerRequest;

import java.util.Base64;

public final class AuthUtil {

    private AuthUtil() {}

    public static Long extractUserId(ServerRequest request) {
        String auth = request.headers().firstHeader("Authorization");
        if (auth == null || !auth.startsWith("Bearer ")) {
            throw new AuthException("Authentication required");
        }
        try {
            String token = auth.substring(7);
            String decoded = new String(Base64.getDecoder().decode(token));
            String[] parts = decoded.split(":");
            return Long.parseLong(parts[0]);
        } catch (Exception e) {
            throw new AuthException("Invalid token");
        }
    }

    public static String encodeToken(Long userId) {
        String payload = userId + ":" + System.currentTimeMillis();
        return Base64.getEncoder().encodeToString(payload.getBytes());
    }
}
