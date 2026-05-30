package com.funrec.common.exception;

public class InferenceException extends RecommendationException {
    public InferenceException(String message) { super(message); }
    public InferenceException(String message, Throwable cause) { super(message, cause); }
}
