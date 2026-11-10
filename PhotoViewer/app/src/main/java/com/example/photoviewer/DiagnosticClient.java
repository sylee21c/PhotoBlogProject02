package com.example.photoviewer;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.charset.StandardCharsets;

/** Raw HTTP diagnostic path so the received request can be compared byte by byte. */
public final class DiagnosticClient {
    private DiagnosticClient() { }
    public static void send(String host, int port, MultipartBody body) throws IOException {
        String method = body == null ? "GET" : "POST";
        String header = method + " /api_root/Post/ HTTP/1.1\r\nHost: " + host + ":" + port
                + "\r\nAccept: application/json\r\nConnection: close\r\n";
        if (body != null) header += "Content-Type: " + body.contentType() + "\r\nContent-Length: " + body.bytes.length + "\r\n";
        header += "\r\n";
        try (Socket socket = new Socket()) {
            socket.connect(new InetSocketAddress(host, port), 10000); socket.setSoTimeout(15000);
            socket.getOutputStream().write(header.getBytes(StandardCharsets.UTF_8));
            if (body != null) socket.getOutputStream().write(body.bytes);
            socket.getOutputStream().flush();
            ByteArrayOutputStream output = new ByteArrayOutputStream(); InputStream input = socket.getInputStream();
            byte[] buffer = new byte[4096]; int count;
            while ((count = input.read(buffer)) != -1) { if(output.size()+count>65536)throw new IOException("Socket 응답이 너무 큽니다.");output.write(buffer,0,count); }
            String response = output.toString(StandardCharsets.UTF_8.name());
            if (!response.startsWith("HTTP/1.1 200 ") && !response.startsWith("HTTP/1.1 201 ")) throw new IOException("Socket 서버가 요청을 수신하지 못했습니다.");
        }
    }
}
