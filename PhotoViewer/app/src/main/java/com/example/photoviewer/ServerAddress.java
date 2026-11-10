package com.example.photoviewer;

import java.net.URI;

/** The Android emulator's localhost is the emulator, not the development PC. */
public final class ServerAddress {
    public static final String DEFAULT = "http://10.0.2.2:8002";
    private ServerAddress() { }
    public static String normalize(String value) {
        String text = value.trim();
        while (text.endsWith("/")) text = text.substring(0, text.length() - 1);
        try {
            URI uri = URI.create(text);
            if (!("https".equals(uri.getScheme()) || "http".equals(uri.getScheme()))
                    || uri.getHost() == null || uri.getUserInfo() != null
                    || uri.getQuery() != null || uri.getFragment() != null
                    || (uri.getPath() != null && !uri.getPath().isEmpty())
                    || uri.getPort() > 65535 || uri.getPort() == 0)
                throw new IllegalArgumentException();
            return text;
        } catch (IllegalArgumentException error) {
            throw new IllegalArgumentException("http://10.0.2.2:8002 또는 https://계정.pythonanywhere.com 형태로 입력하세요.");
        }
    }
}
