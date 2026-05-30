package com.rec.repository.config;

import org.apache.ibatis.type.BaseTypeHandler;
import org.apache.ibatis.type.JdbcType;
import org.apache.ibatis.type.MappedTypes;
import java.sql.*;
import java.util.Arrays;

@MappedTypes(String[].class)
public class ArrayTypeHandler extends BaseTypeHandler<String[]> {

    @Override
    public void setNonNullParameter(PreparedStatement ps, int i, String[] parameter, JdbcType jdbcType)
            throws SQLException {
        try {
            ps.setArray(i, ps.getConnection().createArrayOf("text", parameter));
        } catch (SQLException e) {
            ps.setString(i, String.join(",", parameter));
        }
    }

    private String[] getArraySafe(ResultSet rs, String columnName, int columnIndex, boolean byName) throws SQLException {
        // Try PG-native getArray() first
        try {
            Array a = byName ? rs.getArray(columnName) : rs.getArray(columnIndex);
            if (a != null) {
                Object arr = a.getArray();
                if (arr instanceof String[] sa) return sa;
                if (arr instanceof Object[] oa) {
                    return Arrays.stream(oa).map(Object::toString).toArray(String[]::new);
                }
            }
        } catch (SQLException | NumberFormatException ignored) { /* fallback */ }

        // Fallback: getString() — handles PG literal {a,b,c} or H2 a,b,c
        String raw = byName ? rs.getString(columnName) : rs.getString(columnIndex);
        if (raw == null || raw.isBlank()) return null;
        if (raw.startsWith("{") && raw.endsWith("}")) {
            raw = raw.substring(1, raw.length() - 1);
        }
        if (raw.isBlank()) return new String[0];
        return Arrays.stream(raw.split(","))
            .map(String::trim)
            .filter(s -> !s.isEmpty())
            .toArray(String[]::new);
    }

    @Override
    public String[] getNullableResult(ResultSet rs, String columnName) throws SQLException {
        return getArraySafe(rs, columnName, 0, true);
    }

    @Override
    public String[] getNullableResult(ResultSet rs, int columnIndex) throws SQLException {
        return getArraySafe(rs, null, columnIndex, false);
    }

    @Override
    public String[] getNullableResult(CallableStatement cs, int columnIndex) throws SQLException {
        String raw = cs.getString(columnIndex);
        if (raw == null || raw.isBlank()) return null;
        if (raw.startsWith("{") && raw.endsWith("}")) raw = raw.substring(1, raw.length() - 1);
        if (raw.isBlank()) return new String[0];
        return java.util.Arrays.stream(raw.split(",")).map(String::trim).filter(s -> !s.isEmpty()).toArray(String[]::new);
    }
}
