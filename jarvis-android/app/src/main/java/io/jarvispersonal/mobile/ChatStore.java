package io.jarvispersonal.mobile;

import android.content.Context;
import android.util.AtomicFile;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.function.Consumer;

public final class ChatStore {
    static final int MAX_MESSAGES = 100;
    private static final ExecutorService DISK = Executors.newSingleThreadExecutor();
    private final AtomicFile file;
    public ChatStore(Context context) { file=new AtomicFile(new File(context.getFilesDir(),"conversation.json")); }
    public List<ChatMessage> load() {
        List<ChatMessage> messages=new ArrayList<>();
        try {
            if(file.getBaseFile().length()>1024*1024)return messages;
            JSONArray list=new JSONArray(new String(file.readFully(),StandardCharsets.UTF_8));
            for(int i=Math.max(0,list.length()-MAX_MESSAGES);i<list.length();i++) {
                JSONObject m=list.getJSONObject(i);String role=m.getString("role"),text=m.getString("content");
                if((role.equals("user")||role.equals("assistant")) && text.length()<=12000)messages.add(new ChatMessage(role,text));
            }
        } catch(Exception ignored) { /* An absent or damaged history must not prevent startup. */ }
        return messages;
    }
    public void save(List<ChatMessage> messages) {
        FileOutputStream stream=null;
        try {
            JSONArray list=new JSONArray();
            for(int i=Math.max(0,messages.size()-MAX_MESSAGES);i<messages.size();i++) {
                ChatMessage m=messages.get(i);list.put(new JSONObject().put("role",m.role).put("content",m.content));
            }
            stream=file.startWrite();stream.write(list.toString().getBytes(StandardCharsets.UTF_8));file.finishWrite(stream);
        } catch(Exception e) { if(stream!=null)file.failWrite(stream); }
    }

    public void loadAsync(Consumer<List<ChatMessage>> result) {
        DISK.execute(() -> result.accept(load()));
    }

    public void saveAsync(List<ChatMessage> messages) {
        List<ChatMessage> snapshot = new ArrayList<>(messages);
        DISK.execute(() -> save(snapshot));
    }
}
