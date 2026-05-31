package com.rec.repository.entity;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

@Data
@TableName("ratings")
public class RatingEntity {
    private Long userId;
    private Long movieId;
    @TableField(exist = false)
    private String title;
    private Integer rating;
    private Long timestamp;
}
