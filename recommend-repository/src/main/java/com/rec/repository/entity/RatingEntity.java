package com.rec.repository.entity;

import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

@Data
@TableName("ratings")
public class RatingEntity {
    private Long userId;
    private Long movieId;
    private Integer rating;
    private Long timestamp;
}
