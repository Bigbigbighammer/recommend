package com.funrec.strategy.registry;

import com.funrec.strategy.ranking.RankingStrategy;
import org.springframework.stereotype.Component;

import java.util.List;

@Component
public class RankingStrategyRegistry {

    private final List<RankingStrategy> strategies;

    public RankingStrategyRegistry(List<RankingStrategy> strategies) {
        this.strategies = strategies;
    }

    public List<RankingStrategy> getActiveStrategies() {
        return strategies;
    }
}
