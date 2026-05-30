package com.funrec.repository.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.funrec.repository.entity.GenreEntity;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;
import java.util.List;

@Mapper
public interface GenreMapper extends BaseMapper<GenreEntity> {
    @Select("SELECT name FROM genres ORDER BY name")
    List<String> findAllNames();
}
