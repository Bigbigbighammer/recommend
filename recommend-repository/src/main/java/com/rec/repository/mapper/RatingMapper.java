package com.rec.repository.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.rec.repository.entity.RatingEntity;
import org.apache.ibatis.annotations.*;

import java.util.List;

@Mapper
public interface RatingMapper extends BaseMapper<RatingEntity> {

    @Select("SELECT * FROM ratings WHERE user_id = #{userId} AND movie_id = #{movieId}")
    RatingEntity findByUserAndMovie(@Param("userId") Long userId, @Param("movieId") Long movieId);

    @Select("SELECT r.user_id, r.movie_id, m.title, r.rating, r.timestamp " +
            "FROM ratings r JOIN movies m ON r.movie_id = m.movie_id " +
            "WHERE r.user_id = #{userId} ORDER BY r.timestamp DESC LIMIT #{limit}")
    List<RatingEntity> findRecentByUser(@Param("userId") Long userId, @Param("limit") int limit);

    @Select("SELECT COUNT(*) FROM ratings WHERE user_id = #{userId}")
    int countByUser(@Param("userId") Long userId);

    @Delete("DELETE FROM ratings WHERE user_id = #{userId} AND movie_id = #{movieId}")
    int deleteByUserAndMovie(@Param("userId") Long userId, @Param("movieId") Long movieId);

    @Select("SELECT COALESCE(AVG(rating), 0) FROM ratings WHERE movie_id = #{movieId}")
    Double avgRatingByMovie(@Param("movieId") Long movieId);

    @Select("SELECT COUNT(*) FROM ratings WHERE movie_id = #{movieId}")
    int countByMovie(@Param("movieId") Long movieId);
}
