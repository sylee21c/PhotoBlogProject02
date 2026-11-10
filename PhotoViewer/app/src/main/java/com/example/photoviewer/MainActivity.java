package com.example.photoviewer;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.text.Editable;
import android.text.TextWatcher;
import android.util.LruCache;
import android.view.Gravity;
import android.view.View;
import android.view.WindowInsets;
import android.view.inputmethod.EditorInfo;
import android.widget.*;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.*;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Java native client. Network and decoding work never run on the UI thread. */
public class MainActivity extends Activity {
    private static final int PICK_PHOTO = 42;
    private static final int INK = 0xff183b38, GREEN = 0xff245f51, MUTED = 0xff71827e, PAPER = 0xfff6f8f4;
    private final ExecutorService network = Executors.newFixedThreadPool(3);
    private final ExecutorService photos = Executors.newFixedThreadPool(2);
    private final List<Post> posts = new ArrayList<>();
    private final LruCache<String, Bitmap> images = new LruCache<String, Bitmap>(24 * 1024 * 1024) {
        @Override protected int sizeOf(String key, Bitmap value) { return value.getByteCount(); }
    };
    private SharedPreferences prefs;
    private TokenVault vault;
    private CacheStore feedCache, photoCache;
    private long userId = -1;
    private int loadedPage, totalPosts;
    private boolean hasNext;
    private String activeQuery = "", activeOrdering = "newest";
    private String base, token, ordering = "newest", draftTitle = "", draftText = "";
    private TextView status, serverLabel, count;
    private EditText search;
    private LinearLayout list;
    private Button sync, upload, loadMore;
    private Spinner sort;
    private CheckBox favorites;
    private Uri selectedPhoto;
    private int generation;
    private boolean syncing, hadSynced;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        prefs = getSharedPreferences("photoblog", MODE_PRIVATE);
        base = prefs.getString("server", ServerAddress.DEFAULT);
        vault = new TokenVault(prefs); token = vault.load(base); userId = prefs.getLong("user_id", -1);
        feedCache = new CacheStore(new java.io.File(getFilesDir(),"feed-cache"),4*1024*1024);
        photoCache = new CacheStore(new java.io.File(getCacheDir(),"photo-cache"),32*1024*1024);
        readDraft();
        if (state != null) {
            draftTitle = state.getString("draftTitle", ""); draftText = state.getString("draftText", "");
            String uri = state.getString("photo"); if (uri != null) selectedPhoto = Uri.parse(uri);
            hadSynced = state.getBoolean("synced");
        }
        buildScreen();
        if (state != null) search.setText(state.getString("query", ""));
        if (hadSynced) synchronize(); else loadCachedFeed();
        if (state != null && selectedPhoto != null) showUpload();
    }

    private void buildScreen() {
        LinearLayout root = column(); root.setBackgroundColor(PAPER);
        if (android.os.Build.VERSION.SDK_INT >= 30) {
            root.setOnApplyWindowInsetsListener((view, insets) -> {
                android.graphics.Insets bars = insets.getInsets(WindowInsets.Type.systemBars());
                view.setPadding(bars.left, bars.top, bars.right, bars.bottom); return insets;
            });
        }
        setContentView(root);
        LinearLayout header = row(); header.setGravity(Gravity.CENTER_VERTICAL); pad(header, 22, 16);
        TextView brand = label("PhotoViewer", 22, INK, true);
        header.addView(brand, new LinearLayout.LayoutParams(0, -2, 1));
        Button settings = button("설정", false); settings.setId(R.id.settings);
        settings.setContentDescription("서버 설정 및 로그인"); settings.setOnClickListener(v -> showSettings());
        header.addView(settings); root.addView(header);
        LinearLayout intro = column(); pad(intro, 24, 6);
        serverLabel = label(base, 11, MUTED, false); pad(serverLabel, 0, 5); intro.addView(serverLabel); root.addView(intro);
        LinearLayout actions = row(); pad(actions, 20, 10);
        sync = button("↻ 동기화", true); sync.setId(R.id.sync); sync.setOnClickListener(v -> synchronize());
        upload = button("＋ 새 사진 게시", false); upload.setId(R.id.upload); upload.setOnClickListener(v -> {
            if(selectedPhoto!=null)new AlertDialog.Builder(this).setTitle("작성 중인 사진이 있어요").setItems(new String[]{"초안 이어쓰기","다른 사진 선택"},(dialog,index)->{if(index==0)showUpload();else choosePhoto();}).show();
            else choosePhoto();
        });
        actions.addView(sync, new LinearLayout.LayoutParams(0, dp(48), 1));
        LinearLayout.LayoutParams right = new LinearLayout.LayoutParams(0, dp(48), 1); right.leftMargin = dp(10);
        actions.addView(upload, right); root.addView(actions);
        LinearLayout filters = row(); pad(filters, 20, 4);
        search = edit("제목·내용 검색", false); search.setSingleLine(); search.setId(R.id.search);
        search.setTextSize(13); search.setImeOptions(EditorInfo.IME_ACTION_SEARCH);
        search.setOnEditorActionListener((view, action, event) -> { if (action == EditorInfo.IME_ACTION_SEARCH) { synchronize(); return true; } return false; });
        filters.addView(search, new LinearLayout.LayoutParams(0, dp(46), 1));
        Button find = button("검색", false); find.setOnClickListener(v -> synchronize()); filters.addView(find);
        root.addView(filters);
        LinearLayout options = row(); options.setGravity(Gravity.CENTER_VERTICAL); pad(options, 20, 0);
        favorites = new CheckBox(this); favorites.setText("즐겨찾기만"); favorites.setId(R.id.favorites); favorites.setTextSize(12); favorites.setTextColor(INK);
        favorites.setOnCheckedChangeListener((view, checked) -> renderPosts());
        options.addView(favorites, new LinearLayout.LayoutParams(0, dp(44), 1));
        sort = new Spinner(this);
        sort.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, new String[]{"최신순", "오래된순", "제목순"}));
        sort.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            public void onNothingSelected(AdapterView<?> parent) { }
            public void onItemSelected(AdapterView<?> parent, View view, int index, long id) {
                String next = new String[]{"newest", "oldest", "title"}[index];
                boolean changed = !ordering.equals(next); ordering = next; if (changed && hadSynced) synchronize();
            }
        }); options.addView(sort); root.addView(options);
        status = label("동기화를 누르면 서버의 사진을 가져옵니다.", 12, MUTED, false); status.setId(R.id.status); pad(status, 24, 4); root.addView(status);
        count = label("전체 사진 · 0개", 13, INK, true); pad(count, 24, 8); root.addView(count);
        ScrollView scroll = new ScrollView(this); scroll.setFillViewport(true);
        list = column(); list.setId(R.id.photo_list); pad(list, 20, 4); scroll.addView(list);
        root.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1)); renderPosts();
        loadMore=button("다음 사진 더 불러오기",false);loadMore.setVisibility(View.GONE);loadMore.setOnClickListener(v->{if(!syncing)loadPage(false);});
        root.addView(loadMore,new LinearLayout.LayoutParams(-1,dp(46)));
    }

    private ApiClient api() { return new ApiClient(base, token); }
    private void synchronize() {
        loadPage(true);
    }
    private void loadPage(boolean reset) {
        syncing = true; sync.setEnabled(false); status.setTextColor(MUTED); status.setText("서버에서 사진 목록을 가져오는 중…");
        if(loadMore!=null)loadMore.setEnabled(false);
        int request = ++generation; String server = base, credential = token;
        String query = reset ? search.getText().toString().trim() : activeQuery, order = reset ? ordering : activeOrdering;
        int page = reset ? 1 : loadedPage+1;
        network.execute(() -> {
            try {
                PostPage result = new ApiClient(server, credential).page(query, order, page);
                ui(() -> { if (request != generation) return; if(reset)posts.clear();
                    Set<Long> ids=new HashSet<>();for(Post item:posts)ids.add(item.id);for(Post item:result.items)if(ids.add(item.id))posts.add(item);
                    loadedPage=page;totalPosts=result.total;hasNext=result.hasNext;activeQuery=query;activeOrdering=order;
                    hadSynced = true; syncing = false; sync.setEnabled(true);if(loadMore!=null)loadMore.setEnabled(true);
                    status.setText("동기화 완료 · " + posts.size() + "/"+totalPosts+"개의 사진 · " + new java.text.SimpleDateFormat("HH:mm", Locale.KOREA).format(new Date()));
                    renderPosts();saveFeed(); });
            } catch (Exception error) { ui(() -> { if (request != generation) return; syncing = false; sync.setEnabled(true);if(loadMore!=null)loadMore.setEnabled(true);failure(error); }); }
        });
    }

    private void renderPosts() {
        if (list == null) return;
        list.removeAllViews(); int visible = 0; String currentServer = base; int currentGeneration = generation;
        for (Post post : posts) {
            if (favorites.isChecked() && !isFavorite(post)) continue;
            visible++;
            LinearLayout card = column(); card.setBackground(shape(Color.WHITE, 14));
            LinearLayout.LayoutParams cardParams = new LinearLayout.LayoutParams(-1, -2); cardParams.bottomMargin = dp(16); list.addView(card, cardParams);
            ImageView photo = new ImageView(this); photo.setScaleType(ImageView.ScaleType.CENTER_CROP); photo.setBackgroundColor(0xffdfe7df); photo.setContentDescription(post.title);
            card.addView(photo, new LinearLayout.LayoutParams(-1, dp(205)));
            String key = currentServer + "|" + post.image; Bitmap cached = images.get(key);
            if (cached != null) photo.setImageBitmap(cached);
            else photos.execute(() -> {
                try { Bitmap bitmap = new ApiClient(currentServer, "", photoCache).image(post.image); images.put(key, bitmap);
                    ui(() -> { if (currentServer.equals(base)) photo.setImageBitmap(bitmap); });
                } catch (Exception error) { ui(() -> {photo.setContentDescription(post.title + " · 사진 다운로드 실패");photo.setOnClickListener(v->toast("사진을 받지 못했습니다. 네트워크 연결 후 다시 동기화하세요."));}); }
            });
            photo.setOnClickListener(v -> { Bitmap bitmap = images.get(key); if (bitmap != null) {
                ImageView full = new ImageView(this); full.setImageBitmap(bitmap); full.setAdjustViewBounds(true); full.setScaleType(ImageView.ScaleType.FIT_CENTER);
                new AlertDialog.Builder(this).setTitle(post.title).setView(full).setPositiveButton("닫기", null).show(); }});
            LinearLayout body = column(); pad(body, 17, 14); card.addView(body);
            body.addView(label(post.date + " · " + post.author, 11, MUTED, false));
            LinearLayout titleRow = row(); titleRow.setGravity(Gravity.CENTER_VERTICAL);
            titleRow.addView(label(post.title, 19, INK, true), new LinearLayout.LayoutParams(0, -2, 1));
            Button star = button(isFavorite(post) ? "★" : "☆", false); star.setTextSize(24); star.setContentDescription(post.title + " 즐겨찾기");
            star.setOnClickListener(v -> { String favoriteKey = favoriteKey(post); prefs.edit().putBoolean(favoriteKey, !isFavorite(post)).apply(); renderPosts(); });
            titleRow.addView(star, new LinearLayout.LayoutParams(dp(52), dp(44))); body.addView(titleRow);
            TextView text = label(post.text, 13, MUTED, false); text.setMaxLines(3); body.addView(text);
            if(!token.isEmpty() && userId==post.authorId) {
                LinearLayout manage=row();Button modify=button("수정",false),remove=button("삭제",false);
                modify.setContentDescription(post.title+" 수정");remove.setContentDescription(post.title+" 삭제");
                modify.setOnClickListener(v->editPost(post));remove.setOnClickListener(v->deletePost(post));
                manage.addView(modify,new LinearLayout.LayoutParams(0,dp(40),1));manage.addView(remove,new LinearLayout.LayoutParams(0,dp(40),1));body.addView(manage);
            }
        }
        count.setText((favorites.isChecked() ? "즐겨찾기" : "전체 사진") + " · " + visible + "개");
        if(loadMore!=null)loadMore.setVisibility(hasNext ? View.VISIBLE : View.GONE);
        if (visible == 0) {
            LinearLayout empty = column(); pad(empty, 20, 45); empty.setGravity(Gravity.CENTER);
            empty.addView(label("▧", 48, 0xffb5c7bb, false));
            empty.addView(label(favorites.isChecked() ? "불러온 사진 중 즐겨찾기가 없어요." : hadSynced ? "표시할 사진이 없어요." : "아직 불러온 사진이 없어요.", 15, INK, true));
            TextView hint = label(hadSynced ? "검색어를 바꾸거나 새 사진을 게시해 보세요." : "위의 동기화 버튼으로 시작하세요.", 12, MUTED, false); pad(hint, 0, 8); empty.addView(hint); list.addView(empty);
        }
    }
    private String favoriteKey(Post post) { return "favorite|" + base + "|" + post.id; }
    private boolean isFavorite(Post post) { return prefs.getBoolean(favoriteKey(post), false); }

    private void choosePhoto() {
        if (token.isEmpty()) { toast("사진 게시를 위해 설정에서 먼저 로그인하세요."); showSettings(); return; }
        Intent pick = new Intent(Intent.ACTION_OPEN_DOCUMENT); pick.setType("image/*"); pick.addCategory(Intent.CATEGORY_OPENABLE);
        pick.putExtra(Intent.EXTRA_MIME_TYPES, new String[]{"image/jpeg", "image/png", "image/webp"});
        pick.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
        startActivityForResult(pick, PICK_PHOTO);
    }
    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request == PICK_PHOTO && result == RESULT_OK && data != null && data.getData() != null) {
            selectedPhoto = data.getData();
            try { getContentResolver().takePersistableUriPermission(selectedPhoto, Intent.FLAG_GRANT_READ_URI_PERMISSION); } catch (SecurityException ignored) { }
            persistDraft();showUpload();
        }
    }
    private void showUpload() {
        if (selectedPhoto == null) return;
        LinearLayout content = column(); pad(content, 22, 8);
        ScrollView formScroll=new ScrollView(this);formScroll.addView(content);
        ImageView preview = new ImageView(this); preview.setScaleType(ImageView.ScaleType.FIT_CENTER); preview.setBackground(shape(PAPER, 10));
        content.addView(preview, new LinearLayout.LayoutParams(-1, dp(150)));
        EditText title = edit("제목 (최대 200자)", false); title.setText(draftTitle); content.addView(title);
        TextView titleCount = label("", 11, MUTED, false); content.addView(titleCount);
        EditText text = edit("내용 (최대 5000자)", false); text.setMinLines(2); text.setText(draftText); content.addView(text);
        TextView textCount = label("", 11, MUTED, false); content.addView(textCount);
        TextView guide = label("JPEG · PNG · WebP / 최대 10 MB", 11, MUTED, false); content.addView(guide);
        watch(title, titleCount, 200, value -> draftTitle = value); watch(text, textCount, 5000, value -> draftText = value);
        Uri photoUri = selectedPhoto; String server = base, credential = token;
        final byte[][] photoData = {null}; final String[] photoMime = {null};
        AlertDialog dialog = new AlertDialog.Builder(this).setTitle("새 사진 게시").setView(formScroll).setNegativeButton("닫기 · 초안 저장", null).setNeutralButton("초안 삭제",(d,w)->clearDraft()).setPositiveButton("업로드", null).create();
        dialog.setOnShowListener(v -> {
            Button send = dialog.getButton(AlertDialog.BUTTON_POSITIVE); send.setEnabled(false);
            send.setOnClickListener(clicked -> {
                String t = title.getText().toString().trim(), body = text.getText().toString().trim();
                if (t.isEmpty() || t.codePointCount(0,t.length()) > 200) { title.setError("제목을 1~200자로 입력하세요."); return; }
                if (body.isEmpty() || body.codePointCount(0,body.length()) > 5000) { text.setError("내용을 1~5000자로 입력하세요."); return; }
                send.setEnabled(false); send.setText("업로드 중…"); dialog.getButton(AlertDialog.BUTTON_NEGATIVE).setEnabled(false); dialog.getButton(AlertDialog.BUTTON_NEUTRAL).setEnabled(false); dialog.setCancelable(false);
                network.execute(() -> {
                    try {
                        String extension = "image/png".equals(photoMime[0]) ? ".png" : "image/webp".equals(photoMime[0]) ? ".webp" : ".jpg";
                        MultipartBody multipart = new MultipartBody(MultipartBody.fields(t, body), "photo" + extension, photoMime[0], photoData[0]);
                        new ApiClient(server, credential).upload(multipart);
                        ui(() -> { dialog.dismiss(); clearDraft();toast("사진을 게시했습니다."); status.setText("업로드 완료"); synchronize(); });
                    } catch (Exception error) { ui(() -> { send.setEnabled(true); send.setText("다시 업로드"); dialog.getButton(AlertDialog.BUTTON_NEGATIVE).setEnabled(true);dialog.getButton(AlertDialog.BUTTON_NEUTRAL).setEnabled(true); dialog.setCancelable(true); guide.setText(errorMessage(error)); guide.setTextColor(0xffb43a33); }); }
                });
            });
        }); dialog.show();
        photos.execute(() -> {
            try {
                String mime = getContentResolver().getType(photoUri);
                if (!Arrays.asList("image/jpeg", "image/png", "image/webp").contains(mime)) throw new IllegalArgumentException("JPEG, PNG, WebP 사진을 선택하세요.");
                InputStream input = getContentResolver().openInputStream(photoUri); if (input == null) throw new IllegalArgumentException("사진을 읽을 수 없습니다.");
                byte[] data = ApiClient.read(input, 10 * 1024 * 1024);
                BitmapFactory.Options options = new BitmapFactory.Options(); options.inJustDecodeBounds = true; BitmapFactory.decodeByteArray(data, 0, data.length, options);
                if (options.outWidth <= 0 || (long) options.outWidth * options.outHeight > 40_000_000L) throw new IllegalArgumentException("4천만 화소 이하의 사진을 선택하세요.");
                options.inSampleSize = 1; while (options.outWidth / options.inSampleSize > 1000 || options.outHeight / options.inSampleSize > 1000) options.inSampleSize *= 2;
                options.inJustDecodeBounds = false; Bitmap bitmap = BitmapFactory.decodeByteArray(data, 0, data.length, options);
                photoData[0] = data; photoMime[0] = mime;
                ui(() -> { preview.setImageBitmap(bitmap); dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(true); });
            } catch (Exception error) { ui(() -> { guide.setText(errorMessage(error)); guide.setTextColor(0xffb43a33); }); }
        });
    }

    private void showSettings() {
        LinearLayout fields = column(); pad(fields, 22, 6);
        ScrollView settingsScroll=new ScrollView(this);settingsScroll.addView(fields);
        fields.addView(label("서버 주소", 13, INK, true));
        EditText server = edit("https://계정.pythonanywhere.com", false); server.setId(R.id.server_url); server.setText(base); server.setSingleLine(); fields.addView(server);
        fields.addView(label("에뮬레이터: http://10.0.2.2:8002\n클라우드: 본인의 PythonAnywhere HTTPS 주소", 11, MUTED, false));
        EditText username = edit("아이디", false); username.setSingleLine(); username.setText(prefs.getString("username", "")); fields.addView(username);
        EditText password = edit("비밀번호 (저장하지 않음)", true); fields.addView(password);
        TextView feedback = label(token.isEmpty() ? "로그인하면 새 사진을 게시할 수 있어요." : "로그인됨 · " + prefs.getString("username", ""), 12, GREEN, false); pad(feedback, 0, 8); fields.addView(feedback);
        LinearLayout actions = row(); Button check = button("연결 확인", false), login = button("로그인", true); actions.addView(check); actions.addView(login); fields.addView(actions);
        Button logout = button("로그아웃", false); fields.addView(logout);
        Button capture = button("요청 메시지 검증 (Socket :8001)", false); fields.addView(capture);
        AlertDialog dialog = new AlertDialog.Builder(this).setTitle("서버 설정 · 로그인").setView(settingsScroll).setNegativeButton("닫기", null).setPositiveButton("주소 저장", null).create();
        dialog.setOnShowListener(v -> dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(clicked -> {
            try { saveServer(server.getText().toString()); feedback.setText("서버 주소를 저장했습니다."); dialog.dismiss(); }
            catch (IllegalArgumentException error) { server.setError(error.getMessage()); }
        }));
        check.setOnClickListener(v -> {
            try { String address = ServerAddress.normalize(server.getText().toString()); check.setEnabled(false); feedback.setText("서버 연결 확인 중…");
                network.execute(() -> { try { String result = new ApiClient(address, "").health(); ui(() -> { feedback.setText(result); check.setEnabled(true); }); }
                    catch (Exception error) { ui(() -> { feedback.setText(errorMessage(error)); check.setEnabled(true); }); } });
            } catch (IllegalArgumentException error) { server.setError(error.getMessage()); }
        });
        login.setOnClickListener(v -> {
            try {
                String address = ServerAddress.normalize(server.getText().toString()), name = username.getText().toString().trim(), secret = password.getText().toString();
                if (name.isEmpty() || secret.isEmpty()) { feedback.setText("아이디와 비밀번호를 입력하세요."); return; }
                login.setEnabled(false); feedback.setText("로그인 중…");
                network.execute(() -> { try { String credential = new ApiClient(address, "").login(name, secret);
                    JSONObject profile=new ApiClient(address,credential).profile();
                    vault.save(address,credential);
                    ui(() -> { boolean changedServer=!base.equals(address);if(changedServer) {
                        // saveServer clears credentials; restore the just-encrypted token afterwards.
                        saveServer(address);
                        try {vault.save(address,credential);}catch(Exception error){feedback.setText("암호화 저장에 실패했습니다. 다시 로그인하세요.");login.setEnabled(true);return;}
                    }
                    token = credential;userId=profile.optLong("id",-1);prefs.edit().putString("username",name).putLong("user_id",userId).apply();password.setText(""); feedback.setText("로그인 완료 · " + name); login.setEnabled(true);renderPosts(); });
                } catch (Exception error) { ui(() -> { feedback.setText(errorMessage(error)); login.setEnabled(true); }); } });
            } catch (IllegalArgumentException error) { server.setError(error.getMessage()); }
        });
        logout.setOnClickListener(v -> { token = "";userId=-1;vault.clear();feedback.setText("로그아웃했습니다.");renderPosts(); });
        capture.setOnClickListener(v -> { capture.setEnabled(false); feedback.setText("Socket 서버에 GET·multipart POST 전송 중…");
            network.execute(() -> { try {
                Uri parsed = Uri.parse(base);
                DiagnosticClient.send(parsed.getHost(), 8001, null);
                Bitmap sample = Bitmap.createBitmap(32, 32, Bitmap.Config.ARGB_8888); sample.eraseColor(GREEN);
                ByteArrayOutputStream out = new ByteArrayOutputStream(); sample.compress(Bitmap.CompressFormat.PNG, 100, out); sample.recycle();
                DiagnosticClient.send(parsed.getHost(), 8001, new MultipartBody(MultipartBody.fields("Socket 요청 검증", "Android multipart 전송 검증"), "socket-test.png", "image/png", out.toByteArray()));
                ui(() -> { feedback.setText("GET·POST 전송 완료. PC의 evidence/socket 파일을 확인하세요."); capture.setEnabled(true); });
            } catch (Exception error) { ui(() -> { feedback.setText(errorMessage(error)); capture.setEnabled(true); }); } });
        }); dialog.show();
    }

    private void saveServer(String value) {
        String next = ServerAddress.normalize(value);
        if (!base.equals(next)) {
            persistDraft();base = next; token = "";userId=-1;vault.clear();generation++; syncing = false; hadSynced = false;hasNext=false;loadedPage=0;totalPosts=0;sync.setEnabled(true);posts.clear();images.evictAll();
            prefs.edit().putString("server", base).apply();readDraft();
            serverLabel.setText(base); status.setText("서버 주소 변경 완료. 동기화를 눌러 주세요."); renderPosts();
        }
    }
    private String draftKey() { return "draft|"+base; }
    private void persistDraft() {
        if(prefs==null || base==null)return;
        prefs.edit().putString(draftKey()+"|title",draftTitle).putString(draftKey()+"|text",draftText)
                .putString(draftKey()+"|uri",selectedPhoto==null?"":selectedPhoto.toString()).apply();
    }
    private void readDraft() {
        draftTitle=prefs.getString(draftKey()+"|title","");draftText=prefs.getString(draftKey()+"|text","");
        String uri=prefs.getString(draftKey()+"|uri","");selectedPhoto=uri.isEmpty()?null:Uri.parse(uri);
    }
    private void clearDraft() {
        draftTitle="";draftText="";selectedPhoto=null;
        prefs.edit().remove(draftKey()+"|title").remove(draftKey()+"|text").remove(draftKey()+"|uri").apply();
    }
    private void saveFeed() {
        try {
            JSONArray rows=new JSONArray();for(Post post:posts)rows.put(post.json());
            JSONObject snapshot=new JSONObject().put("query",activeQuery).put("ordering",activeOrdering).put("page",loadedPage)
                    .put("total",totalPosts).put("next",hasNext).put("saved_at",System.currentTimeMillis()).put("posts",rows);
            String server=base;byte[] data=snapshot.toString().getBytes(StandardCharsets.UTF_8);
            network.execute(()->{try {feedCache.put("feed|"+server,data);}catch(Exception ignored){}});
        }catch(Exception ignored){ }
    }
    private void loadCachedFeed() {
        String server=base;int request=generation;
        network.execute(()->{
            try {
                byte[] data=feedCache.get("feed|"+server);if(data==null)return;
                JSONObject snapshot=new JSONObject(new String(data,StandardCharsets.UTF_8));JSONArray rows=snapshot.getJSONArray("posts");
                List<Post> saved=new ArrayList<>();for(int i=0;i<rows.length();i++)saved.add(new Post(rows.getJSONObject(i)));
                ui(()->{if(request!=generation || !base.equals(server))return;
                    posts.clear();posts.addAll(saved);hadSynced=true;loadedPage=snapshot.optInt("page",1);totalPosts=snapshot.optInt("total",saved.size());hasNext=snapshot.optBoolean("next");
                    activeQuery=snapshot.optString("query","");activeOrdering=snapshot.optString("ordering","newest");ordering=activeOrdering;
                    search.setText(activeQuery);sort.setSelection("oldest".equals(ordering)?1:"title".equals(ordering)?2:0);
                    status.setText("저장된 목록 · "+saved.size()+"개 · 동기화로 최신 상태 확인");renderPosts();
                });
            }catch(Exception ignored){ }
        });
    }
    private void editPost(Post post) {
        LinearLayout content=column();pad(content,22,8);ScrollView scroll=new ScrollView(this);scroll.addView(content);
        EditText title=edit("수정할 제목",false);title.setText(post.title);content.addView(title);
        EditText text=edit("수정할 내용",false);text.setMinLines(3);text.setText(post.text);content.addView(text);
        TextView message=label("사진은 유지하고 제목과 내용을 수정합니다.",12,MUTED,false);content.addView(message);
        AlertDialog dialog=new AlertDialog.Builder(this).setTitle("게시글 수정").setView(scroll).setNegativeButton("취소",null).setPositiveButton("수정 저장",null).create();
        String server=base,credential=token;
        dialog.setOnShowListener(v->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(button->{
            String t=title.getText().toString().trim(),body=text.getText().toString().trim();
            if(t.isEmpty() || t.codePointCount(0,t.length())>200){title.setError("제목을 1~200자로 입력하세요.");return;}
            if(body.isEmpty() || body.codePointCount(0,body.length())>5000){text.setError("내용을 1~5000자로 입력하세요.");return;}
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(false);dialog.setCancelable(false);
            dialog.getButton(AlertDialog.BUTTON_NEGATIVE).setEnabled(false);
            network.execute(()->{try {new ApiClient(server,credential).update(post.id,t,body);ui(()->{dialog.dismiss();synchronize();toast("수정했습니다.");});}
                catch(Exception error){ui(()->{message.setText(errorMessage(error));message.setTextColor(0xffb43a33);dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(true);dialog.getButton(AlertDialog.BUTTON_NEGATIVE).setEnabled(true);dialog.setCancelable(true);});}});
        }));dialog.show();
    }
    private void deletePost(Post post) {
        new AlertDialog.Builder(this).setTitle("이 사진을 삭제할까요?").setMessage(post.title+"\n게시글과 사진을 삭제합니다. 이 작업은 되돌릴 수 없습니다.")
                .setNegativeButton("취소",null).setPositiveButton("삭제 확인",(dialog,which)->{
                    String server=base,credential=token;
                    network.execute(()->{try {new ApiClient(server,credential).delete(post.id);ui(()->{prefs.edit().remove(favoriteKey(post)).apply();synchronize();toast("삭제했습니다.");});}
                        catch(Exception error){ui(()->failure(error));}});
                }).show();
    }
    private void failure(Exception error) { status.setTextColor(0xffb43a33);status.setText(errorMessage(error) + (posts.isEmpty()?"":" · 저장된 사진 "+posts.size()+"개 유지")+" · 동기화로 재시도"); }
    private String errorMessage(Exception error) {
        if (error instanceof java.net.SocketTimeoutException) return "연결 시간이 초과됐습니다. 서버 실행과 네트워크를 확인하세요.";
        if (error instanceof java.net.ConnectException) return "서버에 연결할 수 없습니다. 서버 실행과 주소를 확인하세요.";
        return error.getMessage() == null ? "요청을 완료하지 못했습니다." : error.getMessage();
    }
    private interface Changed { void accept(String value); }
    private void watch(EditText input, TextView counter, int max, Changed changed) {
        Runnable update = () -> { String value = input.getText().toString(); int length = value.codePointCount(0, value.length()); counter.setText(length + " / " + max); counter.setTextColor(length > max ? 0xffb43a33 : MUTED); changed.accept(value);persistDraft(); };
        input.addTextChangedListener(new TextWatcher() { public void beforeTextChanged(CharSequence s,int a,int c,int f){} public void onTextChanged(CharSequence s,int a,int b,int c){update.run();} public void afterTextChanged(Editable e){} }); update.run();
    }
    private LinearLayout column() { LinearLayout view = new LinearLayout(this); view.setOrientation(LinearLayout.VERTICAL); return view; }
    private LinearLayout row() { LinearLayout view = new LinearLayout(this); view.setOrientation(LinearLayout.HORIZONTAL); return view; }
    private TextView label(String text, int size, int color, boolean bold) { TextView view = new TextView(this); view.setText(text); view.setTextSize(size); view.setTextColor(color); if (bold) view.setTypeface(null, Typeface.BOLD); return view; }
    private EditText edit(String hint, boolean secret) { EditText input = new EditText(this); input.setHint(hint); input.setTextSize(14); input.setTextColor(INK); input.setPadding(dp(10),dp(10),dp(10),dp(10)); if (secret) input.setInputType(129); return input; }
    private Button button(String text, boolean primary) { Button button = new Button(this); button.setText(text); button.setAllCaps(false); button.setTextSize(13); button.setTextColor(primary ? Color.WHITE : GREEN); button.setBackground(shape(primary ? GREEN : 0xffe8eee6, 10)); button.setPadding(dp(12),0,dp(12),0); return button; }
    private GradientDrawable shape(int color,int radius) { GradientDrawable drawable = new GradientDrawable(); drawable.setColor(color); drawable.setCornerRadius(dp(radius)); return drawable; }
    private int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }
    private void pad(View view,int x,int y) { view.setPadding(dp(x),dp(y),dp(x),dp(y)); }
    private void ui(Runnable action) { runOnUiThread(() -> { if (!isFinishing() && !isDestroyed()) action.run(); }); }
    private void toast(String message) { Toast.makeText(this,message,Toast.LENGTH_LONG).show(); }
    @Override protected void onSaveInstanceState(Bundle state) { super.onSaveInstanceState(state); state.putString("draftTitle",draftTitle); state.putString("draftText",draftText); state.putString("query",search.getText().toString()); state.putBoolean("synced",hadSynced); if(selectedPhoto!=null)state.putString("photo",selectedPhoto.toString()); }
    @Override protected void onDestroy() { persistDraft();network.shutdownNow();photos.shutdownNow();images.evictAll(); super.onDestroy(); }
}
