package io.jarvispersonal.mobile;

import android.content.Context;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/** The API credential is encrypted with a key that never leaves Android Keystore. */
public final class KeyVault {
    private static final String ALIAS="jarvis_groq_v1";
    private final android.content.SharedPreferences prefs;
    public KeyVault(Context context) { prefs=context.getSharedPreferences("vault",Context.MODE_PRIVATE); }
    private SecretKey key() throws Exception {
        KeyStore store=KeyStore.getInstance("AndroidKeyStore"); store.load(null);
        if(store.containsAlias(ALIAS))return (SecretKey)store.getKey(ALIAS,null);
        KeyGenerator gen=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore");
        gen.init(new KeyGenParameterSpec.Builder(ALIAS,KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build());
        return gen.generateKey();
    }
    public synchronized void save(String value) throws Exception {
        if(value.isBlank()) { prefs.edit().clear().apply(); return; }
        Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding"); cipher.init(Cipher.ENCRYPT_MODE,key());
        String encrypted=Base64.encodeToString(cipher.doFinal(value.getBytes(StandardCharsets.UTF_8)),Base64.NO_WRAP);
        prefs.edit().putString("iv",Base64.encodeToString(cipher.getIV(),Base64.NO_WRAP)).putString("cipher",encrypted).apply();
    }
    public synchronized String load() throws Exception {
        if(!prefs.contains("cipher"))return "";
        Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE,key(),new GCMParameterSpec(128,Base64.decode(prefs.getString("iv",""),Base64.NO_WRAP)));
        return new String(cipher.doFinal(Base64.decode(prefs.getString("cipher",""),Base64.NO_WRAP)),StandardCharsets.UTF_8);
    }
    public boolean available() { return prefs.contains("cipher"); }
}
