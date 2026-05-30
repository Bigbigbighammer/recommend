package com.rec.repository.entity;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import com.rec.repository.config.ArrayTypeHandler;
import lombok.Data;

@Data
@TableName("name_basics")
public class NameBasicsEntity {
    private String nconst;
    private String primaryName;
    private Integer birthYear;
    private Integer deathYear;

    @TableField(typeHandler = ArrayTypeHandler.class)
    private String[] primaryProfession;

    @TableField(typeHandler = ArrayTypeHandler.class)
    private String[] knownForTitles;
}
