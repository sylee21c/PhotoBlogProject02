package com.example.photoviewer;

import org.json.JSONException;
import org.json.JSONObject;

public final class Post {
    public final long id;
    public final long authorId;
    public final String title, text, image, author, date;
    public Post(JSONObject json) throws JSONException {
        id = json.getLong("id");
        authorId = json.optLong("author", -1);
        title = json.getString("title");
        text = json.optString("text");
        image = json.optString("image");
        author = json.optString("author_name", "작성자");
        String raw = json.optString("published_date", "");
        date = raw.length() >= 10 ? raw.substring(0, 10).replace('-', '.') : raw;
    }
    public JSONObject json() throws JSONException {
        return new JSONObject().put("id",id).put("author",authorId).put("author_name",author).put("title",title).put("text",text).put("image",image).put("published_date",date);
    }
}
