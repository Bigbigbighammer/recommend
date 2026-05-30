package com.rec.repository.entity;

import com.baomidou.mybatisplus.annotation.*;
import com.rec.repository.config.ArrayTypeHandler;
import lombok.Data;

@Data
@TableName(value = "movies", autoResultMap = true)
public class MovieEntity {
    @TableId(type = IdType.AUTO)
    private Long movieId;
    private String imdbId;
    private String title;
    private Integer year;

    @TableField(typeHandler = ArrayTypeHandler.class)
    private String[] genres;

    private String description;
    private Double avgRating;
    private Integer ratingCount;
    private Double imdbRating;
    private Integer imdbVotes;
    private String titleType;
    private Integer runtimeMinutes;
    private Integer isAdult;
    private String posterUrl;
    private Long createdBy;
}
