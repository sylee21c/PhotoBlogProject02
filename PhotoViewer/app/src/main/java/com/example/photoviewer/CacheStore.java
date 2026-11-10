package com.example.photoviewer;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.Comparator;

/** Bounded, atomic, app-private cache. Keys never become filesystem paths. */
public final class CacheStore {
    private final File directory;
    private final long limit;
    public CacheStore(File directory, long limit) { this.directory = directory; this.limit = limit; }
    private File file(String key) throws IOException {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(key.getBytes(StandardCharsets.UTF_8));
            StringBuilder name = new StringBuilder(); for (byte value : digest) name.append(String.format("%02x", value & 255));
            return new File(directory, name + ".cache");
        } catch (java.security.NoSuchAlgorithmException error) { throw new IOException(error); }
    }
    public synchronized byte[] get(String key) throws IOException {
        File target = file(key);
        if (!target.exists()) return null;
        if (target.length() > limit) { target.delete(); return null; }
        byte[] data = Files.readAllBytes(target.toPath()); target.setLastModified(System.currentTimeMillis()); return data;
    }
    public synchronized void put(String key, byte[] data) throws IOException {
        if (data.length > limit) return;
        if (!directory.exists() && !directory.mkdirs()) throw new IOException("캐시 폴더를 만들 수 없습니다.");
        File target = file(key), temporary = File.createTempFile("write-", ".tmp", directory);
        try {
            try (FileOutputStream output = new FileOutputStream(temporary)) { output.write(data); output.getFD().sync(); }
            Files.move(temporary.toPath(), target.toPath(), StandardCopyOption.REPLACE_EXISTING);
        } finally { temporary.delete(); }
        File[] files = directory.listFiles((folder, name) -> name.endsWith(".cache"));
        if (files == null) return;
        Arrays.sort(files, Comparator.comparingLong(File::lastModified));
        long total = 0; for (File entry : files) total += entry.length();
        for (File entry : files) { if (total <= limit) break; if (!entry.equals(target)) { long size = entry.length(); if(entry.delete())total -= size; } }
    }
}
