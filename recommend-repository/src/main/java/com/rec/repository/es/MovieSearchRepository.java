package com.rec.repository.es;

import org.springframework.data.elasticsearch.core.ReactiveElasticsearchOperations;
import org.springframework.data.elasticsearch.core.SearchHit;
import org.springframework.data.elasticsearch.core.query.Criteria;
import org.springframework.data.elasticsearch.core.query.CriteriaQuery;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Flux;

import java.util.List;

@Component
public class MovieSearchRepository {

    private final ReactiveElasticsearchOperations es;

    public MovieSearchRepository(ReactiveElasticsearchOperations es) {
        this.es = es;
    }

    public Flux<MovieSearchResult> searchByGenres(List<String> genres, int topK) {
        CriteriaQuery query;
        if (genres == null || genres.isEmpty()) {
            Criteria criteria = new Criteria("avgRating").greaterThanEqual(5);
            query = new CriteriaQuery(criteria);
        } else {
            Criteria criteria = new Criteria("genres").in(genres)
                .and(new Criteria("avgRating").greaterThanEqual(5));
            query = new CriteriaQuery(criteria);
        }
        query.setMaxResults(topK);
        return es.search(query, MovieSearchResult.class)
            .map(SearchHit::getContent);
    }

    public Flux<MovieSearchResult> searchByKeyword(String keyword, int from, int size) {
        Criteria criteria = new Criteria("title").matches(keyword)
            .or(new Criteria("description").matches(keyword));
        CriteriaQuery query = new CriteriaQuery(criteria);
        query.setMaxResults(size);
        return es.search(query, MovieSearchResult.class)
            .map(SearchHit::getContent);
    }

    public Flux<MovieSearchResult> suggest(String prefix, int limit) {
        Criteria criteria = new Criteria("title").startsWith(prefix);
        CriteriaQuery query = new CriteriaQuery(criteria);
        query.setMaxResults(limit);
        return es.search(query, MovieSearchResult.class)
            .map(SearchHit::getContent);
    }
}
