package com.example.photoviewer;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

/** Explicit CRLF and binary image bytes, matching the HTTP multipart lesson. */
public final class MultipartBody {
    public final String boundary;
    public final byte[] bytes;
    public MultipartBody(Map<String, String> fields, String filename, String mime, byte[] image) throws IOException {
        boundary = "PhotoViewer" + UUID.randomUUID().toString().replace("-", "");
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        for (Map.Entry<String, String> item : fields.entrySet()) {
            if (!item.getKey().matches("[a-zA-Z0-9_]+")) throw new IllegalArgumentException("Invalid field name");
            write(out, "--" + boundary + "\r\nContent-Disposition: form-data; name=\"" + item.getKey() + "\"\r\n\r\n" + item.getValue() + "\r\n");
        }
        String safe = filename.replaceAll("[\\r\\n\\\"\\\\/]", "_");
        if (!mime.matches("image/(jpeg|png|webp)")) throw new IllegalArgumentException("JPEG, PNG, WebP 사진을 선택하세요.");
        write(out, "--" + boundary + "\r\nContent-Disposition: form-data; name=\"image\"; filename=\"" + safe + "\"\r\nContent-Type: " + mime + "\r\n\r\n");
        out.write(image);
        write(out, "\r\n--" + boundary + "--\r\n");
        bytes = out.toByteArray();
    }
    private static void write(ByteArrayOutputStream out, String value) throws IOException {
        out.write(value.getBytes(StandardCharsets.UTF_8));
    }
    public String contentType() { return "multipart/form-data; boundary=" + boundary; }
    public static Map<String, String> fields(String title, String text) {
        Map<String, String> fields = new LinkedHashMap<>();
        fields.put("title", title);
        fields.put("text", text);
        return fields;
    }
}
