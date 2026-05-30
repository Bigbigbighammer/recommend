package com.rec.repository.entity;

import com.baomidou.mybatisplus.annotation.*;
import com.rec.repository.config.ArrayTypeHandler;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("users")
public class UserEntity {
    @TableId(type = IdType.AUTO)
    private Long userId;
    private String email;
    private String username;
    private String hashedPassword;
    private Integer isActive;
    private Integer isSuperuser;
    private String gender;
    private String age;
    private String occupation;
    private String zipCode;
    private LocalDateTime createdAt;

    @TableField(typeHandler = ArrayTypeHandler.class)
    private String[] preferredGenres;
}
