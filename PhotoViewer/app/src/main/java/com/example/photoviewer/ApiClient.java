package com.example.photoviewer;

import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

/** All methods are blocking and are called only on a background executor. */
public final class ApiClient {
    private final String base, token;
    private final CacheStore imageCache;
    public ApiClient(String base, String token) { this(base,token,null); }
    public ApiClient(String base, String token, CacheStore imageCache) { this.base = base; this.token = token; this.imageCache=imageCache; }

    public static final class ApiException extends IOException {
        public final int status;
        public ApiException(int status,String message) { super(message);this.status=status; }
    }

    public String request(String method, String path, byte[] body, String contentType) throws IOException {
        HttpURLConnection connection = (HttpURLConnection) new URL(base + path).openConnection();
        try {
            connection.setConnectTimeout(12000);
            connection.setReadTimeout(20000);
            // Never forward a token or an upload to a different redirect destination.
            connection.setInstanceFollowRedirects(false);
            connection.setRequestMethod(method);
            connection.setRequestProperty("Accept", "application/json");
            if (!token.isEmpty()) connection.setRequestProperty("Authorization", "Token " + token);
            if (body != null) {
                connection.setDoOutput(true);
                connection.setRequestProperty("Content-Type", contentType);
                connection.setFixedLengthStreamingMode(body.length);
                try (java.io.OutputStream stream = connection.getOutputStream()) { stream.write(body); }
            }
            int status = connection.getResponseCode();
            InputStream stream = status >= 400 ? connection.getErrorStream() : connection.getInputStream();
            String result = stream == null ? "" : new String(read(stream, 4 * 1024 * 1024), StandardCharsets.UTF_8);
            if (status < 200 || status >= 300) {
                if (status == 401 || status == 403) throw new ApiException(status,"로그인이 필요하거나 권한이 없습니다. 설정에서 다시 로그인하세요. (HTTP " + status + ")");
                if (status == 400) throw new ApiException(status,"입력 내용을 확인하세요. " + result);
                if (status == 404) throw new ApiException(status,"게시글이나 페이지를 찾을 수 없습니다. 목록을 새로 동기화하세요.");
                throw new ApiException(status,"서버 응답 오류 HTTP " + status + ". 주소와 서버 상태를 확인하세요.");
            }
            return result;
        } finally { connection.disconnect(); }
    }
    public List<Post> posts(String query, String ordering) throws Exception {
        String path = "/api_root/Post/?q=" + URLEncoder.encode(query, "UTF-8") + "&ordering=" + ordering;
        String raw = request("GET", path, null, null);
        JSONArray rows = new JSONArray(raw);
        List<Post> result = new ArrayList<>();
        for (int i = 0; i < rows.length(); i++) result.add(new Post(rows.getJSONObject(i)));
        return result;
    }
    public String login(String username, String password) throws Exception {
        JSONObject fields = new JSONObject().put("username", username).put("password", password);
        return new JSONObject(request("POST", "/api/token/", fields.toString().getBytes(StandardCharsets.UTF_8), "application/json")).getString("token");
    }
    public JSONObject profile() throws Exception { return new JSONObject(request("GET","/api/me/",null,null)); }
    public PostPage page(String query,String ordering,int page) throws Exception {
        String raw=request("GET","/api_root/Post/?page="+page+"&page_size=12&q="+URLEncoder.encode(query,"UTF-8")+"&ordering="+ordering,null,null);
        JSONObject json=new JSONObject(raw);JSONArray rows=json.getJSONArray("results");List<Post> items=new ArrayList<>();
        for(int i=0;i<rows.length();i++)items.add(new Post(rows.getJSONObject(i)));
        return new PostPage(items,json.getInt("count"),!json.isNull("next"));
    }
    public void update(long id,String title,String text) throws Exception {
        JSONObject fields=new JSONObject().put("title",title).put("text",text);
        request("PATCH","/api_root/Post/"+id+"/",fields.toString().getBytes(StandardCharsets.UTF_8),"application/json");
    }
    public void delete(long id) throws Exception { request("DELETE","/api_root/Post/"+id+"/",null,null); }
    public void upload(MultipartBody body) throws IOException {
        request("POST", "/api_root/Post/", body.bytes, body.contentType());
    }
    public String health() throws Exception {
        JSONObject json = new JSONObject(request("GET", "/api/health/", null, null));
        if (!"ok".equals(json.optString("status"))) throw new IOException("서버 상태를 확인할 수 없습니다.");
        return "연결 성공 · 서버 사진 " + json.optInt("posts") + "개";
    }
    public Bitmap image(String address) throws Exception {
        String cacheKey="image|"+base+"|"+address;
        byte[] saved=null;
        if(imageCache!=null)try { saved=imageCache.get(cacheKey); } catch(IOException ignored) { }
        if(saved!=null) { Bitmap bitmap=decodeImage(saved);if(bitmap!=null)return bitmap; }
        URL source = new URL(address.startsWith("/") ? base + address : address);
        if (!(source.getProtocol().equals("https") || source.getProtocol().equals("http"))) throw new IOException("올바르지 않은 이미지 주소");
        HttpURLConnection connection = (HttpURLConnection) source.openConnection();
        try {
            connection.setConnectTimeout(10000); connection.setReadTimeout(15000);
            if (connection.getResponseCode() != 200) throw new IOException("사진 다운로드 실패");
            byte[] data = read(connection.getInputStream(), 11 * 1024 * 1024);
            Bitmap bitmap = decodeImage(data);
            if (bitmap == null) throw new IOException("사진을 읽을 수 없습니다.");
            if(imageCache!=null)try { imageCache.put(cacheKey,data); } catch(IOException ignored) { }
            return bitmap;
        } finally { connection.disconnect(); }
    }
    private Bitmap decodeImage(byte[] data) {
        BitmapFactory.Options options=new BitmapFactory.Options();options.inJustDecodeBounds=true;
        BitmapFactory.decodeByteArray(data,0,data.length,options);
        if(options.outWidth<=0 || (long)options.outWidth*options.outHeight>40_000_000L)return null;
        options.inSampleSize=1;
        while(options.outWidth/options.inSampleSize>1200 || options.outHeight/options.inSampleSize>1200)options.inSampleSize*=2;
        options.inJustDecodeBounds=false;return BitmapFactory.decodeByteArray(data,0,data.length,options);
    }
    public static byte[] read(InputStream source, int limit) throws IOException {
        try (InputStream input = source; ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192]; int count;
            while ((count = input.read(buffer)) != -1) {
                if (output.size() + count > limit) throw new IOException("파일 크기가 제한을 초과했습니다.");
                output.write(buffer, 0, count);
            }
            return output.toByteArray();
        }
    }
}
