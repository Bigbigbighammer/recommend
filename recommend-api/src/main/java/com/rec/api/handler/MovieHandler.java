package com.rec.api.handler;

import com.rec.common.model.request.MovieCreateRequest;
import com.rec.common.model.response.CastMemberResponse;
import com.rec.common.model.response.MovieCastResponse;
import com.rec.common.model.response.MovieDetailResponse;
import com.rec.common.model.response.MovieListItem;
import com.rec.common.model.response.MovieListResponse;
import com.rec.repository.entity.MovieEntity;
import com.rec.repository.mapper.MovieMapper;
import com.rec.repository.mapper.NameBasicsMapper;
import com.rec.repository.mapper.TitleCrewMapper;
import com.rec.repository.mapper.TitlePrincipalMapper;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.server.ServerRequest;
import org.springframework.web.reactive.function.server.ServerResponse;
import reactor.core.publisher.Mono;

import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Component
public class MovieHandler {

    private final MovieMapper movieMapper;
    private final TitlePrincipalMapper titlePrincipalMapper;
    private final NameBasicsMapper nameBasicsMapper;
    private final TitleCrewMapper titleCrewMapper;

    public MovieHandler(MovieMapper movieMapper, TitlePrincipalMapper titlePrincipalMapper,
                        NameBasicsMapper nameBasicsMapper, TitleCrewMapper titleCrewMapper) {
        this.movieMapper = movieMapper;
        this.titlePrincipalMapper = titlePrincipalMapper;
        this.nameBasicsMapper = nameBasicsMapper;
        this.titleCrewMapper = titleCrewMapper;
    }

    public Mono<ServerResponse> create(ServerRequest request) {
        return request.bodyToMono(MovieCreateRequest.class).flatMap(req -> {
            var movie = new MovieEntity();
            movie.setTitle(req.title());
            movie.setImdbId(req.imdbId());
            movie.setYear(req.year());
            movie.setGenres(req.genres() != null ? req.genres().toArray(String[]::new) : null);
            movie.setDescription(req.description());
            movie.setRuntimeMinutes(req.runtimeMinutes());
            movie.setTitleType(req.titleType());
            movie.setImdbRating(req.imdbRating());
            movie.setImdbVotes(req.imdbVotes());
            movieMapper.insert(movie);
            return ServerResponse.ok().build();
        });
    }

    public Mono<ServerResponse> list(ServerRequest request) {
        int page = Integer.parseInt(request.queryParam("page").orElse("1"));
        int size = Integer.parseInt(request.queryParam("page_size").orElse("20"));
        var movies = movieMapper.selectList(null);
        var items = movies.stream().map(m -> new MovieListItem(m.getMovieId(), m.getTitle(), m.getYear(),
            m.getGenres() != null ? Arrays.asList(m.getGenres()) : List.of(),
            m.getAvgRating(), m.getImdbRating(), m.getPosterUrl())).collect(Collectors.toList());
        return ServerResponse.ok().bodyValue(new MovieListResponse(items, movies.size(), page, size, false));
    }

    public Mono<ServerResponse> popular(ServerRequest request) {
        var movies = movieMapper.findPopular(20);
        var items = movies.stream().map(m -> new MovieListItem(m.getMovieId(), m.getTitle(), m.getYear(),
            m.getGenres() != null ? Arrays.asList(m.getGenres()) : List.of(),
            m.getAvgRating(), m.getImdbRating(), m.getPosterUrl())).collect(Collectors.toList());
        return ServerResponse.ok().bodyValue(items);
    }

    public Mono<ServerResponse> detail(ServerRequest request) {
        Long id = Long.parseLong(request.pathVariable("id"));
        var m = movieMapper.selectById(id);
        if (m == null) return ServerResponse.notFound().build();
        return ServerResponse.ok().bodyValue(new MovieDetailResponse(m.getMovieId(), m.getImdbId(), m.getTitle(),
            m.getYear(), m.getGenres() != null ? Arrays.asList(m.getGenres()) : List.of(),
            m.getDescription(), m.getAvgRating(), m.getRatingCount(),
            m.getImdbRating(), m.getImdbVotes(), m.getRuntimeMinutes(), m.getTitleType(), m.getPosterUrl()));
    }

    public Mono<ServerResponse> cast(ServerRequest request) {
        Long id = Long.parseLong(request.pathVariable("id"));
        var movie = movieMapper.selectById(id);
        if (movie == null || movie.getImdbId() == null) return ServerResponse.notFound().build();
        var principals = titlePrincipalMapper.findByTconst(movie.getImdbId());
        var cast = principals.stream()
            .filter(p -> "actor".equals(p.getCategory()) || "actress".equals(p.getCategory()))
            .map(p -> {
                var nb = nameBasicsMapper.findByNconst(p.getNconst());
                return new CastMemberResponse(p.getNconst(),
                    nb != null ? nb.getPrimaryName() : "", p.getCharacters(), p.getCategory(), p.getOrdering());
            })
            .collect(Collectors.toList());
        return ServerResponse.ok().bodyValue(new MovieCastResponse(id, movie.getTitle(), cast));
    }

    public Mono<ServerResponse> crew(ServerRequest request) {
        Long id = Long.parseLong(request.pathVariable("id"));
        var movie = movieMapper.selectById(id);
        if (movie == null || movie.getImdbId() == null) return ServerResponse.notFound().build();
        var crew = titleCrewMapper.findByTconst(movie.getImdbId());
        String[] directors = crew != null ? toNames(crew.getDirectors()) : new String[]{};
        String[] writers = crew != null ? toNames(crew.getWriters()) : new String[]{};
        return ServerResponse.ok().bodyValue(Map.of(
            "movie_id", id, "movie_title", movie.getTitle(),
            "directors", directors, "writers", writers));
    }

    private String[] toNames(String[] nconsts) {
        if (nconsts == null) return new String[]{};
        return Arrays.stream(nconsts)
            .map(nconst -> {
                var nb = nameBasicsMapper.findByNconst(nconst);
                return nb != null ? nb.getPrimaryName() : nconst;
            })
            .toArray(String[]::new);
    }
}
