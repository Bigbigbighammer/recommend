package com.funrec.repository.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.funrec.repository.entity.RatingEntity;
import org.apache.ibatis.annotations.*;

import java.util.List;

@Mapper
public interface RatingMapper extends BaseMapper<RatingEntity> {

    @Select("SELECT * FROM ratings WHERE user_id = #{userId} AND movie_id = #{movieId}")
    RatingEntity findByUserAndMovie(@Param("userId") Long userId, @Param("movieId") Long movieId);

    @Select("SELECT * FROM ratings WHERE user_id = #{userId} ORDER BY timestamp DESC LIMIT #{limit}")
    List<RatingEntity> findRecentByUser(@Param("userId") Long userId, @Param("limit") int limit);

    @Select("SELECT COUNT(*) FROM ratings WHERE user_id = #{userId}")
    int countByUser(@Param("userId") Long userId);

    @Delete("DELETE FROM ratings WHERE user_id = #{userId} AND movie_id = #{movieId}")
    int deleteByUserAndMovie(@Param("userId") Long userId, @Param("movieId") Long movieId);
}
