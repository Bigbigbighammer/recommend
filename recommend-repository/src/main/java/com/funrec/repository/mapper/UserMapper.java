package com.funrec.repository.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.funrec.repository.entity.UserEntity;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

@Mapper
public interface UserMapper extends BaseMapper<UserEntity> {

    @Select("SELECT * FROM users WHERE email = #{email} AND is_active = 1")
    UserEntity findByEmail(@Param("email") String email);

    @Select("SELECT * FROM users WHERE user_id = #{userId} AND is_active = 1")
    UserEntity findActiveById(@Param("userId") Long userId);
}
