package com.rec.repository.entity;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import com.rec.repository.config.ArrayTypeHandler;
import lombok.Data;

@Data
@TableName(value = "title_crew", autoResultMap = true)
public class TitleCrewEntity {
    private String tconst;

    @TableField(typeHandler = ArrayTypeHandler.class)
    private String[] directors;

    @TableField(typeHandler = ArrayTypeHandler.class)
    private String[] writers;
}
