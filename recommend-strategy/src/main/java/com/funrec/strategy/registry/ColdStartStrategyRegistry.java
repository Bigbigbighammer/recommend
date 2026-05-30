package com.funrec.strategy.registry;

import com.funrec.strategy.coldstart.ColdStartStrategy;
import org.springframework.stereotype.Component;

import java.util.List;

@Component
public class ColdStartStrategyRegistry {

    private final List<ColdStartStrategy> strategies;

    public ColdStartStrategyRegistry(List<ColdStartStrategy> strategies) {
        this.strategies = strategies;
    }

    public List<ColdStartStrategy> getActiveStrategies() {
        return strategies;
    }
}
