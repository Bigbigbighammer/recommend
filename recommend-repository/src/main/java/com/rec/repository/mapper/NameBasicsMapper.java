package com.rec.repository.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.rec.repository.entity.NameBasicsEntity;
import org.apache.ibatis.annotations.*;

@Mapper
public interface NameBasicsMapper extends BaseMapper<NameBasicsEntity> {
    @Select("SELECT * FROM name_basics WHERE nconst = #{nconst}")
    NameBasicsEntity findByNconst(@Param("nconst") String nconst);
}
