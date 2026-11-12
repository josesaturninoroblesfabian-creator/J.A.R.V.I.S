package io.jarvispersonal.mobile;

import android.app.*;
import android.content.*;
import android.os.*;
import android.view.*;
import android.widget.*;

/** Exercises the real Android activity without a test framework or live credentials. */
public final class SmokeInstrumentation extends Instrumentation {
    private Activity activity;
    private int checks;
    private boolean live;
    @Override public void onCreate(Bundle args) { super.onCreate(args);live="true".equals(args.getString("live"));start(); }
    private void check(boolean value,String label) { if(!value)throw new AssertionError(label);checks++; }
    private View find(View root,String value) {
        if(value.equals(root.getContentDescription()))return root;
        if(root instanceof TextView t && value.contentEquals(t.getText()))return root;
        if(root instanceof ViewGroup g)for(int i=0;i<g.getChildCount();i++){View result=find(g.getChildAt(i),value);if(result!=null)return result;}
        return null;
    }
    private View root() { return activity.getWindow().getDecorView(); }
    private void click(String label) { View[] target={null};runOnMainSync(()->target[0]=find(root(),label));check(target[0]!=null,"Control: "+label);runOnMainSync(()->target[0].performClick());waitForIdleSync(); }
    private String allText(View view) { StringBuilder b=new StringBuilder();if(view instanceof TextView t)b.append(t.getText()).append('\n');if(view instanceof ViewGroup g)for(int i=0;i<g.getChildCount();i++)b.append(allText(g.getChildAt(i)));return b.toString(); }
    private void send(String value) { runOnMainSync(()->((EditText)find(root(),"Mensaje para Jarvis")).setText(value));click("Enviar"); }
    private String text() { String[] value={""};runOnMainSync(()->value[0]=allText(root()));return value[0]; }
    private void contains(String value) { check(text().contains(value),"Texto esperado: "+value); }
    @Override public void onStart() {
        Bundle result=new Bundle();
        try {
            Context context=getTargetContext();context.getSharedPreferences("settings",0).edit().clear().putBoolean("read",false).apply();new KeyVault(context).save("");
            var history = new java.util.ArrayList<ChatMessage>();
            for (int i = 0; i < 60; i++) history.add(new ChatMessage("user", "Historial guardado " + i));
            new ChatStore(context).save(history);
            Intent intent=new Intent(context,MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            activity=startActivitySync(intent);
            for (int i = 0; i < 30 && !text().contains("J A R V I S"); i++) Thread.sleep(100);
            waitForIdleSync();contains("J A R V I S");
            contains("Historial guardado 59");
            check(!text().contains("Historial guardado 0\n"), "Se dibujan primero los mensajes recientes");
            click("Ver mensajes anteriores");contains("Historial guardado 12");
            click("Ver mensajes anteriores");contains("Historial guardado 0\n");
            send("calcula 137*29");contains("3973");
            send("recuerda que Quiero estudiar programación");contains("Lo guardé");
            send("mis notas");contains("Quiero estudiar programación");
            send("cambia el holograma a violeta");contains("ahora es violeta");
            send("hola, conversemos");contains("Para conversar necesito tu clave de Groq");
            click("Compañero");contains("Enfoque amable");
            click("25 min");check(context.getSharedPreferences("settings",0).getLong("focus_end",0)>System.currentTimeMillis(),"Enfoque iniciado");
            click("Pausar / seguir");check(context.getSharedPreferences("settings",0).getLong("focus_paused",0)>0,"Enfoque pausado");
            click("Pausar / seguir");check(context.getSharedPreferences("settings",0).getLong("focus_end",0)>System.currentTimeMillis(),"Enfoque reanudado");
            click("Terminar");check(context.getSharedPreferences("settings",0).getLong("focus_end",0)==0,"Enfoque detenido");
            runOnMainSync(()->find(root(),"Encender cámara").requestRectangleOnScreen(new android.graphics.Rect(0,0,100,100)));
            click("Encender cámara");
            for(int i=0;i<16;i++){Thread.sleep(500);waitForIdleSync();if(text().contains("Cámara encendida")||text().contains("presencia detectada"))break;}
            check(text().contains("Cámara encendida")||text().contains("presencia detectada"),"Cámara: "+text());
            click("Apagar cámara");contains("Cámara apagada");
            KeyVault vault=new KeyVault(context);vault.save("test-not-a-real-provider-key");check(vault.load().equals("test-not-a-real-provider-key"),"Keystore cifra y descifra");
            check(!context.getSharedPreferences("vault",0).getString("cipher","").contains("test-not-a-real-provider-key"),"Clave no almacenada en claro");vault.save("");
            click("Ajustes");contains("Hazlo tuyo");
            var saved = new java.util.concurrent.CountDownLatch(1);
            var savedHistory = new java.util.concurrent.atomic.AtomicReference<java.util.List<ChatMessage>>();
            new ChatStore(context).loadAsync(value -> { savedHistory.set(value); saved.countDown(); });
            check(saved.await(5, java.util.concurrent.TimeUnit.SECONDS), "Guardado en segundo plano");
            check(savedHistory.get().size() >= 70, "Historial persistente con mensajes antiguos y nuevos");
            if(live) {
                java.io.File keyFile=new java.io.File(context.getFilesDir(),"qa-key");
                String key=new String(java.nio.file.Files.readAllBytes(keyFile.toPath()),java.nio.charset.StandardCharsets.UTF_8).trim();keyFile.delete();
                java.util.concurrent.CountDownLatch latch=new java.util.concurrent.CountDownLatch(1);
                java.util.concurrent.atomic.AtomicReference<String> outcome=new java.util.concurrent.atomic.AtomicReference<>("");
                new Thread(()->new GroqClient().ask(key,"openai/gpt-oss-20b",java.util.List.of(new ChatMessage("user","Saluda en español en una frase.")),ConversationPolicy.system("","Cercano",""),new GroqClient.Listener(){
                    public void partial(String text){}
                    public void complete(String text){outcome.set(text.isEmpty()?"empty":"ok");latch.countDown();}
                    public void error(String error){outcome.set(error);latch.countDown();}
                })).start();
                check(latch.await(55,java.util.concurrent.TimeUnit.SECONDS),"Respuesta Groq a tiempo");
                check(outcome.get().equals("ok"),"Groq real: "+outcome.get());
            }
            result.putString("stream","JARVIS_SMOKE_OK checks="+checks+" network="+live+"\n");
            runOnMainSync(()->activity.finish());finish(Activity.RESULT_OK,result);
        } catch(Throwable e) { result.putString("stream","JARVIS_SMOKE_FAILED "+e.toString()+"\n");finish(Activity.RESULT_CANCELED,result); }
    }
}
