package com.rec.repository.es;

import org.springframework.data.annotation.Id;
import org.springframework.data.elasticsearch.annotations.Document;
import org.springframework.data.elasticsearch.annotations.Field;
import org.springframework.data.elasticsearch.annotations.FieldType;

import java.util.List;

@Document(indexName = "movies")
public record MovieSearchResult(
    @Id Long movieId,
    @Field(type = FieldType.Text) String title,
    @Field(type = FieldType.Integer) Integer year,
    @Field(type = FieldType.Keyword) List<String> genres,
    @Field(type = FieldType.Float) Double avgRating,
    @Field(type = FieldType.Integer) Integer ratingCount,
    @Field(type = FieldType.Float) Double imdbRating,
    @Field(type = FieldType.Integer) Integer imdbVotes,
    @Field(type = FieldType.Text) String description
) {}
