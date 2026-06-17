package com.rec.repository.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.rec.repository.entity.MovieEntity;
import org.apache.ibatis.annotations.*;

import java.util.List;

@Mapper
public interface MovieMapper extends BaseMapper<MovieEntity> {

    @Select("SELECT * FROM movies ORDER BY avg_rating DESC, rating_count DESC LIMIT #{limit}")
    List<MovieEntity> findPopular(@Param("limit") int limit);

    @Select("SELECT * FROM movies WHERE genres && ARRAY[#{genre}]::text[] " +
            "AND avg_rating >= 5 ORDER BY year DESC, avg_rating DESC LIMIT #{limit}")
    List<MovieEntity> findByGenre(@Param("genre") String genre, @Param("limit") int limit);

    @Select("<script>" +
            "SELECT * FROM movies WHERE genres &amp;&amp; ARRAY[#{genre}]::text[] " +
            "<if test='minRating != null'>AND avg_rating &gt;= #{minRating}</if> " +
            "<if test='yearFrom != null'>AND year &gt;= #{yearFrom}</if> " +
            "<if test='yearTo != null'>AND year &lt;= #{yearTo}</if> " +
            "ORDER BY ${sortColumn} ${sortDir} " +
            "LIMIT #{limit} OFFSET #{offset}" +
            "</script>")
    List<MovieEntity> findByGenrePaged(@Param("genre") String genre,
                                       @Param("minRating") Double minRating,
                                       @Param("yearFrom") Integer yearFrom,
                                       @Param("yearTo") Integer yearTo,
                                       @Param("sortColumn") String sortColumn,
                                       @Param("sortDir") String sortDir,
                                       @Param("offset") int offset,
                                       @Param("limit") int limit);

    @Select("<script>" +
            "SELECT COUNT(*) FROM movies WHERE genres &amp;&amp; ARRAY[#{genre}]::text[] " +
            "<if test='minRating != null'>AND avg_rating &gt;= #{minRating}</if> " +
            "<if test='yearFrom != null'>AND year &gt;= #{yearFrom}</if> " +
            "<if test='yearTo != null'>AND year &lt;= #{yearTo}</if> " +
            "</script>")
    long countByGenreFiltered(@Param("genre") String genre,
                              @Param("minRating") Double minRating,
                              @Param("yearFrom") Integer yearFrom,
                              @Param("yearTo") Integer yearTo);

    @Select("SELECT * FROM movies ORDER BY movie_id ASC LIMIT #{limit} OFFSET #{offset}")
    List<MovieEntity> findPage(@Param("offset") int offset, @Param("limit") int limit);

    @Select("SELECT COUNT(*) FROM movies")
    long countAll();
}
