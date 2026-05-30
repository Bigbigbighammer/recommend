package com.funrec.repository.entity;

import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

@Data
@TableName("title_akas")
public class TitleAkaEntity {
    private String tconst;
    private Integer ordering;
    private String title;
    private String region;
    private String language;
    private String types;
    private String attributes;
    private Integer isOriginalTitle;
}
