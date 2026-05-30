package com.rec.repository.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

@Data
@TableName("genres")
public class GenreEntity {
    @TableId(type = IdType.AUTO)
    private Long id;
    private String name;
}
