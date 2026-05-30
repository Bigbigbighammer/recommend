package com.rec.repository.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.rec.repository.entity.TitleCrewEntity;
import org.apache.ibatis.annotations.*;

@Mapper
public interface TitleCrewMapper extends BaseMapper<TitleCrewEntity> {
    @Select("SELECT * FROM title_crew WHERE tconst = #{tconst}")
    TitleCrewEntity findByTconst(@Param("tconst") String tconst);
}
