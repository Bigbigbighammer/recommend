package com.funrec.repository.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.funrec.repository.entity.MovieEntity;
import org.apache.ibatis.annotations.*;

import java.util.List;

@Mapper
public interface MovieMapper extends BaseMapper<MovieEntity> {

    @Select("SELECT * FROM movies ORDER BY avg_rating DESC, rating_count DESC LIMIT #{limit}")
    List<MovieEntity> findPopular(@Param("limit") int limit);

    @Select("SELECT * FROM movies WHERE genres && ARRAY[#{genre}]::text[] " +
            "AND avg_rating >= 5 ORDER BY year DESC, avg_rating DESC LIMIT #{limit}")
    List<MovieEntity> findByGenre(@Param("genre") String genre, @Param("limit") int limit);
}
