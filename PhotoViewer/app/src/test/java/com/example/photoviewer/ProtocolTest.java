package com.example.photoviewer;

import org.junit.Test;
import java.nio.charset.StandardCharsets;
import static org.junit.Assert.*;

public class ProtocolTest {
    @Test public void normalizesServerRoot() { assertEquals("https://student.pythonanywhere.com", ServerAddress.normalize(" https://student.pythonanywhere.com/// ")); }
    @Test public void acceptsEmulatorPort() { assertEquals("http://10.0.2.2:8000", ServerAddress.normalize("http://10.0.2.2:8000")); }
    @Test public void rejectsNonHttpAndEmbeddedCredentials() {
        for(String input : new String[]{"file:///tmp/a", "https://user:secret@example.com", "http://", "https://example.com/api", "https://example.com?q=1", "http://host:70000"}) {
            try { ServerAddress.normalize(input); fail(input); } catch (IllegalArgumentException expected) { }
        }
    }
    @Test public void multipartPreservesUnicodeAndBinaryAndEndsBoundary() throws Exception {
        byte[] image = {0, 1, 13, 10, (byte)255};
        MultipartBody body = new MultipartBody(MultipartBody.fields("한글 제목", "사진 내용"), "photo.png", "image/png", image);
        String raw = new String(body.bytes, StandardCharsets.UTF_8);
        assertTrue(raw.contains("name=\"title\"\r\n\r\n한글 제목\r\n"));
        assertTrue(raw.contains("Content-Type: image/png\r\n\r\n"));
        assertTrue(raw.endsWith("\r\n--" + body.boundary + "--\r\n"));
        int start = indexOf(body.bytes, "Content-Type: image/png\r\n\r\n".getBytes(StandardCharsets.UTF_8)) + "Content-Type: image/png\r\n\r\n".length();
        assertArrayEquals(image, java.util.Arrays.copyOfRange(body.bytes, start, start + image.length));
    }
    @Test public void filenamesCannotInjectHeaders() throws Exception {
        MultipartBody body = new MultipartBody(MultipartBody.fields("a", "b"), "a\"\r\nEvil:yes.png", "image/png", new byte[]{1});
        assertFalse(new String(body.bytes, StandardCharsets.UTF_8).contains("\r\nEvil"));
    }
    @Test(expected=IllegalArgumentException.class) public void rejectsNonImageMime() throws Exception { new MultipartBody(MultipartBody.fields("a","b"),"x.html","text/html",new byte[]{1}); }
    private int indexOf(byte[] source, byte[] pattern) { outer:for(int i=0;i<=source.length-pattern.length;i++){for(int j=0;j<pattern.length;j++)if(source[i+j]!=pattern[j])continue outer;return i;}return -1; }
}
