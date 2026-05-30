package com.funrec.repository.entity;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import com.funrec.repository.config.ArrayTypeHandler;
import lombok.Data;

@Data
@TableName("title_crew")
public class TitleCrewEntity {
    private String tconst;

    @TableField(typeHandler = ArrayTypeHandler.class)
    private String[] directors;

    @TableField(typeHandler = ArrayTypeHandler.class)
    private String[] writers;
}
