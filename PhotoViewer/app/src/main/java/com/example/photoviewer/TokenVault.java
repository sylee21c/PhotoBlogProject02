package com.example.photoviewer;

import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/** AES-GCM with an Android Keystore key and server origin bound as AAD. */
public final class TokenVault {
    private static final String ALIAS = "PhotoViewer.Auth.v1";
    private final SharedPreferences prefs;
    public TokenVault(SharedPreferences prefs) { this.prefs = prefs; }
    private SecretKey key() throws Exception {
        KeyStore store = KeyStore.getInstance("AndroidKeyStore"); store.load(null);
        if (store.containsAlias(ALIAS)) return (SecretKey) store.getKey(ALIAS, null);
        KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
        generator.init(new KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).setKeySize(256).build());
        return generator.generateKey();
    }
    public void save(String server, String token) throws Exception {
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding"); cipher.init(Cipher.ENCRYPT_MODE, key());
        cipher.updateAAD(server.getBytes(StandardCharsets.UTF_8));
        String ciphertext = Base64.encodeToString(cipher.doFinal(token.getBytes(StandardCharsets.UTF_8)), Base64.NO_WRAP);
        prefs.edit().putString("auth_iv", Base64.encodeToString(cipher.getIV(), Base64.NO_WRAP)).putString("auth_cipher", ciphertext).remove("token").apply();
    }
    public String load(String server) {
        try {
            String old = prefs.getString("token", "");
            if (!old.isEmpty()) { save(server, old); return old; }
            String data = prefs.getString("auth_cipher", ""); if(data.isEmpty())return "";
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.DECRYPT_MODE, key(), new GCMParameterSpec(128, Base64.decode(prefs.getString("auth_iv", ""), Base64.NO_WRAP)));
            cipher.updateAAD(server.getBytes(StandardCharsets.UTF_8));
            return new String(cipher.doFinal(Base64.decode(data, Base64.NO_WRAP)), StandardCharsets.UTF_8);
        } catch (Exception invalidKeyOrData) { clear(); return ""; }
    }
    public void clear() { prefs.edit().remove("token").remove("auth_cipher").remove("auth_iv").remove("username").remove("user_id").apply(); }
}
