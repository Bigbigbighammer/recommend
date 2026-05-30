package com.funrec.strategy.registry;

import com.funrec.strategy.recall.RecallStrategy;
import org.springframework.stereotype.Component;

import java.util.List;

@Component
public class RecallStrategyRegistry {

    private final List<RecallStrategy> strategies;

    public RecallStrategyRegistry(List<RecallStrategy> strategies) {
        this.strategies = strategies;
    }

    public List<RecallStrategy> getActiveStrategies() {
        return strategies;
    }
}
