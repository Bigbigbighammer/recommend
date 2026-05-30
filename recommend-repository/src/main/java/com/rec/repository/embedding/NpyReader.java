package com.rec.repository.embedding;

import java.io.*;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.channels.FileChannel;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public final class NpyReader {

    private static final byte[] MAGIC = {(byte) 0x93, 'N', 'U', 'M', 'P', 'Y'};

    private NpyReader() {}

    public static double[][] loadFloat64(String path) throws IOException {
        try (var raf = new RandomAccessFile(path, "r");
             var ch = raf.getChannel()) {
            ByteBuffer buf = ch.map(FileChannel.MapMode.READ_ONLY, 0, ch.size());
            buf.order(ByteOrder.LITTLE_ENDIAN);

            for (byte b : MAGIC) {
                if (buf.get() != b) throw new IOException("Not an NPY file: " + path);
            }

            int major = buf.get() & 0xFF;
            int minor = buf.get() & 0xFF;
            long headerLen;
            if (major == 1) {
                headerLen = buf.getShort() & 0xFFFF;
            } else if (major == 2 || major == 3) {
                headerLen = buf.getInt() & 0xFFFFFFFFL;
            } else {
                throw new IOException("Unsupported NPY version: " + major + "." + minor);
            }

            byte[] headerBytes = new byte[(int) headerLen];
            buf.get(headerBytes);
            String header = new String(headerBytes, "ASCII").trim();

            String descr = extract(header, "descr");
            if (!"<f8".equals(descr)) {
                throw new IOException("Expected dtype <f8, got: " + descr);
            }
            if ("True".equals(extract(header, "fortran_order"))) {
                throw new IOException("Fortran order not supported");
            }

            String shapeStr = extract(header, "shape");
            if (shapeStr == null || shapeStr.isEmpty()) {
                throw new IOException("Empty shape in NPY file: " + path);
            }

            String[] dims = shapeStr.split(",");
            int rows = Integer.parseInt(dims[0].trim());
            int cols = dims.length > 1 ? Integer.parseInt(dims[1].trim()) : 1;

            double[][] result = new double[rows][cols];
            for (int i = 0; i < rows; i++) {
                for (int j = 0; j < cols; j++) {
                    result[i][j] = buf.getDouble();
                }
            }
            return result;
        }
    }

    public static long[] loadInt64(String path) throws IOException {
        try (var raf = new RandomAccessFile(path, "r");
             var ch = raf.getChannel()) {
            ByteBuffer buf = ch.map(FileChannel.MapMode.READ_ONLY, 0, ch.size());
            buf.order(ByteOrder.LITTLE_ENDIAN);

            for (byte b : MAGIC) {
                if (buf.get() != b) throw new IOException("Not an NPY file: " + path);
            }

            int major = buf.get() & 0xFF;
            buf.get(); // minor
            long headerLen;
            if (major == 1) {
                headerLen = buf.getShort() & 0xFFFF;
            } else {
                headerLen = buf.getInt() & 0xFFFFFFFFL;
            }

            byte[] headerBytes = new byte[(int) headerLen];
            buf.get(headerBytes);
            String header = new String(headerBytes, "ASCII").trim();

            String descr = extract(header, "descr");
            if (!"<i8".equals(descr)) {
                throw new IOException("Expected dtype <i8, got: " + descr);
            }

            String shapeStr = extract(header, "shape");
            int count = Integer.parseInt(shapeStr.split(",")[0].trim());

            long[] result = new long[count];
            for (int i = 0; i < count; i++) {
                result[i] = buf.getLong();
            }
            return result;
        }
    }

    private static String extract(String header, String key) {
        Matcher m = Pattern.compile("'" + key + "':\\s*(.+?)(?:,\\s*'|,\\s*\\})")
                .matcher(header);
        if (!m.find()) return null;
        String val = m.group(1).trim();
        if (val.startsWith("'")) val = val.substring(1, val.length() - 1);
        if (val.startsWith("(") && val.endsWith(")")) val = val.substring(1, val.length() - 1);
        if (val.endsWith(",")) val = val.substring(0, val.length() - 1);
        return val.trim();
    }
}
