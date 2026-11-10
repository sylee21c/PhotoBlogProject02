package com.example.photoviewer;

import org.junit.Test;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import static org.junit.Assert.*;

public class CacheStoreTest {
    @Test public void snapshotsSurviveNewCacheInstanceAndOverwriteAtomically() throws Exception {
        File folder=Files.createTempDirectory("photo-cache-test").toFile();
        try {
            CacheStore cache=new CacheStore(folder,1024);
            assertNull(cache.get("feed|server"));cache.put("feed|server","first".getBytes(StandardCharsets.UTF_8));
            assertEquals("first",new String(new CacheStore(folder,1024).get("feed|server"),StandardCharsets.UTF_8));
            cache.put("feed|server","second".getBytes(StandardCharsets.UTF_8));
            assertEquals("second",new String(cache.get("feed|server"),StandardCharsets.UTF_8));
            assertEquals(1,folder.listFiles().length);
        } finally {for(File f:folder.listFiles())f.delete();folder.delete();}
    }
    @Test public void hostileKeysCannotEscapeAndServersStaySeparate() throws Exception {
        File folder=Files.createTempDirectory("photo-cache-test").toFile();
        try {
            CacheStore cache=new CacheStore(folder,1024);cache.put("../../private",new byte[]{1});cache.put("server-b",new byte[]{2});
            assertArrayEquals(new byte[]{1},cache.get("../../private"));assertArrayEquals(new byte[]{2},cache.get("server-b"));
            for(File f:folder.listFiles())assertTrue(f.getName().matches("[0-9a-f]{64}\\.cache"));
        } finally {for(File f:folder.listFiles())f.delete();folder.delete();}
    }
    @Test public void diskBudgetIsBoundedAndOversizedValuesAreNotStored() throws Exception {
        File folder=Files.createTempDirectory("photo-cache-test").toFile();
        try {
            CacheStore cache=new CacheStore(folder,12);cache.put("one",new byte[8]);Thread.sleep(5);cache.put("two",new byte[8]);
            long bytes=0;for(File f:folder.listFiles())bytes+=f.length();assertTrue(bytes<=12);assertNotNull(cache.get("two"));
            cache.put("too-large",new byte[13]);assertNull(cache.get("too-large"));
        } finally {for(File f:folder.listFiles())f.delete();folder.delete();}
    }
}
