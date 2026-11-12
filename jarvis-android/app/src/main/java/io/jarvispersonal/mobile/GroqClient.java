package io.jarvispersonal.mobile;

import org.json.JSONArray;
import org.json.JSONObject;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.List;
import javax.net.ssl.HttpsURLConnection;

/** One cancellable request at a time, no SDK, no hidden retry or replay of actions. */
public final class GroqClient {
    public interface Listener { void partial(String text); void complete(String text); void error(String message); }
    private volatile HttpsURLConnection connection;
    private volatile boolean cancelled;
    private static volatile long cooldownUntil;
    public void cancel() { cancelled=true; HttpsURLConnection c=connection; if(c!=null)c.disconnect(); }
    public void ask(String key, String model, List<ChatMessage> messages, String system, Listener listener) {
        try {
            if(cancelled)return;
            long wait=(cooldownUntil-System.currentTimeMillis()+999)/1000;
            if(wait>0) { listener.error(RatePolicy.message(wait));return; }
            JSONArray history=new JSONArray().put(new JSONObject().put("role","system").put("content",system));
            for(ChatMessage m:ConversationPolicy.recent(messages))history.put(new JSONObject().put("role",m.role).put("content",m.content));
            JSONObject payload=new JSONObject().put("model",model).put("messages",history).put("stream",true)
                .put("temperature",0.65).put("max_completion_tokens",640).put("reasoning_effort","low");
            HttpsURLConnection c=(HttpsURLConnection)new URL("https://api.groq.com/openai/v1/chat/completions").openConnection();
            connection=c;c.setConnectTimeout(10000);c.setReadTimeout(45000);c.setRequestMethod("POST");c.setDoOutput(true);
            c.setRequestProperty("Authorization","Bearer "+key);c.setRequestProperty("Content-Type","application/json; charset=utf-8");
            c.setRequestProperty("Accept","text/event-stream");
            c.setInstanceFollowRedirects(false);
            if(cancelled)return;
            try(OutputStream output=c.getOutputStream()) { output.write(payload.toString().getBytes(StandardCharsets.UTF_8)); }
            int code=c.getResponseCode();
            if(code==429) { long seconds=RatePolicy.seconds(c.getHeaderField("retry-after"));cooldownUntil=System.currentTimeMillis()+seconds*1000;listener.error(RatePolicy.message(seconds));return; }
            if(code==401) { listener.error("La clave de Groq no es válida. Revísala en Ajustes.");return; }
            if(code==403) { listener.error("Tu cuenta no tiene acceso a ese modelo. Prueba el otro cerebro en Ajustes.");return; }
            if(code!=200) { listener.error("Groq no pudo responder ("+code+"). Inténtalo más tarde o cambia de modelo.");return; }
            StringBuilder answer=new StringBuilder();boolean ended=false;
            try(BufferedReader reader=new BufferedReader(new InputStreamReader(c.getInputStream(),StandardCharsets.UTF_8))) {
                String line;
                long lastUpdate = 0;
                int publishedLength = 0;
                while(!cancelled && (line=reader.readLine())!=null) {
                    if(line.length()>65536)throw new IllegalStateException("Respuesta demasiado grande");
                    if(!line.startsWith("data:"))continue;
                    String data=line.substring(5).trim();if(data.equals("[DONE]")) { ended=true;break; }
                    JSONObject chunk=new JSONObject(data);
                    if(chunk.has("error"))throw new IllegalStateException("Respuesta del proveedor incompleta");
                    JSONArray choices=chunk.optJSONArray("choices");if(choices==null||choices.length()==0)continue;
                    JSONObject choice=choices.getJSONObject(0),delta=choice.optJSONObject("delta");
                    if(delta!=null && !delta.isNull("content"))answer.append(delta.optString("content",""));
                    if(answer.length()>12000)throw new IllegalStateException("Respuesta demasiado grande");
                    if(!choice.isNull("finish_reason"))ended=true;
                    long now = android.os.SystemClock.elapsedRealtime();
                    if (answer.length() != publishedLength && now - lastUpdate >= 90) {
                        listener.partial(answer.toString());
                        publishedLength = answer.length();
                        lastUpdate = now;
                    }
                }
            }
            if(!cancelled) {
                if(!ended)listener.error("La conexión se interrumpió. Tu petición no se repetirá automáticamente.");
                else if(answer.toString().trim().isEmpty())listener.error("El modelo no devolvió texto. Prueba el otro cerebro en Ajustes.");
                else listener.complete(answer.toString().trim());
            }
        } catch(Exception e) { if(!cancelled)listener.error("No pude conectar con Groq. Revisa Internet y vuelve a intentarlo."); }
        finally { HttpsURLConnection c=connection;connection=null;if(c!=null)c.disconnect(); }
    }
}
