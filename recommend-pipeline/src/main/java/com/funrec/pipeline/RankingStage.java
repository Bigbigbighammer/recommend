package com.funrec.pipeline;

import com.funrec.common.model.pipeline.*;
import com.funrec.repository.mapper.MovieMapper;
import com.funrec.repository.entity.MovieEntity;
import com.funrec.strategy.registry.RankingStrategyRegistry;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;

import java.util.*;
import java.util.stream.Collectors;

@Component
public class RankingStage {
    private final RankingStrategyRegistry registry;
    private final MovieMapper movieMapper;

    public RankingStage(RankingStrategyRegistry registry, MovieMapper movieMapper) {
        this.registry = registry;
        this.movieMapper = movieMapper;
    }

    public Mono<PipelineContext> execute(PipelineContext ctx, int topK) {
        List<Long> movieIds = ctx.recallCandidates().stream()
            .map(RecallItem::movieId).collect(Collectors.toList());
        Map<Long, ItemFeatures> itemFeaturesMap = fetchItemFeatures(movieIds);

        var strategies = registry.getActiveStrategies();
        if (strategies.isEmpty()) {
            return Mono.just(ctx.withRankedItems(
                ctx.recallCandidates().stream()
                    .map(c -> new RankedItem(c.movieId(), c.score(), c.score(), c.recallType(), List.of(), 0))
                    .limit(topK).toList()
            ).withItemFeatures(itemFeaturesMap));
        }

        var primary = strategies.get(0);
        return primary.rank(ctx.recallCandidates(), ctx.userFeatures(), itemFeaturesMap)
            .onErrorResume(e -> {
                if (strategies.size() > 1) {
                    return strategies.get(1).rank(ctx.recallCandidates(), ctx.userFeatures(), itemFeaturesMap);
                }
                return Mono.just(ctx.recallCandidates().stream()
                    .map(c -> new RankedItem(c.movieId(), c.score(), c.score(), c.recallType(), List.of(), 0))
                    .toList());
            })
            .map(items -> items.stream().limit(topK).toList())
            .map(ctx::withRankedItems)
            .map(c -> c.withItemFeatures(itemFeaturesMap));
    }

    private Map<Long, ItemFeatures> fetchItemFeatures(List<Long> movieIds) {
        Map<Long, ItemFeatures> map = new HashMap<>();
        for (Long id : movieIds) {
            MovieEntity m = movieMapper.selectById(id);
            if (m != null) {
                map.put(id, new ItemFeatures(
                    m.getGenres() != null && m.getGenres().length > 0 ? m.getGenres()[0] : null,
                    m.getGenres() != null ? Arrays.asList(m.getGenres()) : List.of(),
                    m.getIsAdult() != null ? m.getIsAdult() : 0,
                    m.getYear() != null ? m.getYear() : 0));
            }
        }
        return map;
    }
}
