package com.rec.strategy.registry;

import com.rec.strategy.reranking.RerankingStrategy;
import org.springframework.stereotype.Component;

import java.util.List;

@Component
public class RerankingStrategyRegistry {

    private final List<RerankingStrategy> strategies;

    public RerankingStrategyRegistry(List<RerankingStrategy> strategies) {
        this.strategies = strategies;
    }

    public List<RerankingStrategy> getActiveStrategies() {
        return strategies;
    }
}
