package com.rec.repository.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.rec.repository.entity.TitlePrincipalEntity;
import org.apache.ibatis.annotations.*;
import java.util.List;

@Mapper
public interface TitlePrincipalMapper extends BaseMapper<TitlePrincipalEntity> {
    @Select("SELECT * FROM title_principals WHERE tconst = #{tconst} ORDER BY ordering")
    List<TitlePrincipalEntity> findByTconst(@Param("tconst") String tconst);
}
