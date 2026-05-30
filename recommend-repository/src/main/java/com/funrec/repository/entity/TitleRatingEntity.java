package com.funrec.repository.entity;

import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

@Data
@TableName("title_ratings")
public class TitleRatingEntity {
    private String tconst;
    private Double averageRating;
    private Integer numVotes;
}
