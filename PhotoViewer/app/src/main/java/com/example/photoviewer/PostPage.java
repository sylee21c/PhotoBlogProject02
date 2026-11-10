package com.example.photoviewer;

import java.util.List;
public final class PostPage {
    public final List<Post> items;
    public final int total;
    public final boolean hasNext;
    public PostPage(List<Post> items, int total, boolean hasNext) { this.items=items;this.total=total;this.hasNext=hasNext; }
}
