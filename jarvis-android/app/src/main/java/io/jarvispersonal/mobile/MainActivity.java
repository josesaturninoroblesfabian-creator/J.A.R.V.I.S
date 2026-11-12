package io.jarvispersonal.mobile;

import android.Manifest;
import android.app.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CameraManager;
import android.os.*;
import android.speech.*;
import android.speech.tts.*;
import android.text.InputFilter;
import android.text.InputType;
import android.view.*;
import android.view.inputmethod.InputMethodManager;
import android.widget.*;
import java.text.DateFormat;
import java.util.*;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class MainActivity extends Activity {
    private static final int BG=0xff0b101c, CARD=0xff141e30, TEXT=0xffedf4ff, MUTED=0xffa4b3cb, ACCENT=0xff5ee1f2;
    private static final int HISTORY_PAGE_SIZE = 24;
    private android.content.SharedPreferences prefs;
    private KeyVault vault;
    private ChatStore store;
    private final List<ChatMessage> messages=new ArrayList<>();
    private final ExecutorService network=Executors.newSingleThreadExecutor();
    private final Handler handler=new Handler(Looper.getMainLooper());
    private GroqClient client=new GroqClient();
    private TextToSpeech tts;
    private SpeechRecognizer recognizer;
    private boolean voiceReady, listening, busy, resumed, destroyed;
    private int requestId, selectedTab;
    private int visibleHistory = HISTORY_PAGE_SIZE;
    private boolean scrollPending;
    private String utterance="", torchId;
    private LinearLayout root, chatMessages, chatPage, companionPage, settingsPage, cameraBox;
    private FrameLayout pages;
    private ScrollView chatScroll;
    private TextView status, liveReply, focusClock, focusLabel, cameraStatus, credentialStatus;
    private EditText composer, keyInput, nameInput, notesInput, goalInput;
    private Button send, mic, cameraButton, olderMessages;
    private Switch readSwitch, shareNotes;
    private Spinner modelChoice, styleChoice;
    private OrbView orb, companionOrb;
    private CameraPreview preview;
    private final Runnable ticker = this::updateFocus;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);prefs=getSharedPreferences("settings",MODE_PRIVATE);vault=new KeyVault(this);store=new ChatStore(this);
        store.loadAsync(history -> handler.post(() -> {
            if (destroyed) return;
            messages.addAll(history);
            buildUi();
            initVoice();
            FocusReceiver.channel(this);
            setStatus(vault.available() ? "Aquí contigo · listo para ayudarte"
                : "Tu espacio está listo · conecta Groq en Ajustes", "idle");
            if (resumed) restoreFocus();
        }));
    }
    private int dp(float n) { return Math.round(n*getResources().getDisplayMetrics().density); }
    private GradientDrawable background(int color,int radius) { GradientDrawable b=new GradientDrawable();b.setColor(color);b.setCornerRadius(dp(radius));return b; }
    private LinearLayout column() { LinearLayout v=new LinearLayout(this);v.setOrientation(LinearLayout.VERTICAL);return v; }
    private LinearLayout row() { LinearLayout v=new LinearLayout(this);v.setOrientation(LinearLayout.HORIZONTAL);v.setGravity(Gravity.CENTER_VERTICAL);return v; }
    private TextView text(String value,int size,int color) { TextView t=new TextView(this);t.setText(value);t.setTextSize(size);t.setTextColor(color);t.setLineSpacing(dp(3),1);return t; }
    private TextView heading(String value,int size) { TextView t=text(value,size,TEXT);t.setTypeface(null,Typeface.BOLD);return t; }
    private void gap(LinearLayout p,int h) { View v=new View(this);p.addView(v,new LinearLayout.LayoutParams(1,dp(h))); }
    private Button button(String value,Runnable action) { Button b=new Button(this);b.setText(value);b.setAllCaps(false);b.setTextColor(TEXT);b.setTextSize(14);b.setMinHeight(dp(48));b.setPadding(dp(12),dp(6),dp(12),dp(6));b.setBackground(background(0xff223149,14));b.setOnClickListener(v->action.run());return b; }
    private void buttonRow(LinearLayout parent,Button... buttons) { LinearLayout r=row();for(Button b:buttons) { LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(0,dp(48),1);p.setMargins(dp(3),dp(3),dp(3),dp(3));r.addView(b,p); }parent.addView(r); }
    private EditText input(String hint,int max) { EditText e=new EditText(this);e.setTextColor(TEXT);e.setHintTextColor(MUTED);e.setTextSize(16);e.setHint(hint);e.setPadding(dp(14),dp(12),dp(14),dp(12));e.setBackground(background(CARD,14));e.setFilters(new InputFilter[]{new InputFilter.LengthFilter(max)});e.setMinHeight(dp(50));return e; }
    private ScrollView scroll(LinearLayout content) { ScrollView s=new ScrollView(this);s.setFillViewport(true);s.setClipToPadding(false);s.addView(content,new ScrollView.LayoutParams(-1,-2));return s; }
    private LinearLayout card(LinearLayout parent,String title,String subtitle) { LinearLayout c=column();c.setPadding(dp(16),dp(16),dp(16),dp(16));c.setBackground(background(CARD,20));parent.addView(c,new LinearLayout.LayoutParams(-1,-2));c.addView(heading(title,19));gap(c,6);if(!subtitle.isEmpty())c.addView(text(subtitle,14,MUTED));gap(c,12);return c; }
    private void buildUi() {
        root=column();root.setBackgroundColor(BG);root.setPadding(dp(18),dp(12),dp(18),dp(8));setContentView(root);
        getWindow().getInsetsController().setSystemBarsAppearance(0,WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS|WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS);
        root.setOnApplyWindowInsetsListener((v,insets)-> { var bars=insets.getInsets(WindowInsets.Type.systemBars());var ime=insets.getInsets(WindowInsets.Type.ime());v.setPadding(dp(18)+bars.left,dp(10)+bars.top,dp(18)+bars.right,dp(6)+Math.max(bars.bottom,ime.bottom));return insets; });
        LinearLayout header=row();LinearLayout brand=column();brand.addView(heading("J A R V I S",23));brand.addView(text("TU COMPAÑERO PERSONAL",10,MUTED));header.addView(brand,new LinearLayout.LayoutParams(0,-2,1));orb=new OrbView(this);header.addView(orb,new LinearLayout.LayoutParams(dp(64),dp(64)));root.addView(header);
        status=text("Preparando tu espacio…",12,ACCENT);status.setPadding(0,0,0,dp(10));status.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);root.addView(status);
        pages=new FrameLayout(this);root.addView(pages,new LinearLayout.LayoutParams(-1,0,1));
        buildChat();buildCompanion();
        LinearLayout nav=row();String[] labels={"Conversación","Compañero","Ajustes"};
        for(int i=0;i<labels.length;i++) { final int tab=i;Button b=button(labels[i],()->showTab(tab));b.setTextSize(12);LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(0,dp(50),1);p.setMargins(dp(2),dp(6),dp(2),0);nav.addView(b,p); }
        root.addView(nav);showTab(0);applyColor(prefs.getString("color","azul"));root.requestApplyInsets();
    }
    private void buildChat() {
        chatPage=column();LinearLayout tools=row();tools.addView(text("UN PASO A LA VEZ",11,MUTED),new LinearLayout.LayoutParams(0,-2,1));
        Button fresh=button("Nuevo",()->new AlertDialog.Builder(this).setTitle("¿Nueva conversación?").setMessage("Se borrará el chat de este teléfono. Tus notas se conservan.").setNegativeButton("Conservar",null).setPositiveButton("Nueva",(d,w)->clearConversation()).show());fresh.setTextSize(12);tools.addView(fresh,new LinearLayout.LayoutParams(dp(80),dp(42)));chatPage.addView(tools);
        olderMessages = button("Ver mensajes anteriores", this::showOlderMessages);
        chatPage.addView(olderMessages);
        chatMessages=column();chatMessages.setPadding(0,dp(12),0,dp(12));chatScroll=scroll(chatMessages);chatPage.addView(chatScroll,new LinearLayout.LayoutParams(-1,0,1));
        LinearLayout quick=row();String[] labels={"Enfocarme","¿Qué puedes hacer?"};String[] commands={"inicia enfoque de 25 minutos","qué puedes hacer"};for(int i=0;i<labels.length;i++){final String cmd=commands[i];Button b=button(labels[i],()->submit(cmd));b.setTextSize(12);LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(0,dp(44),1);p.setMargins(dp(2),0,dp(2),dp(6));quick.addView(b,p);}chatPage.addView(quick);
        composer=input("Escribe o habla con Jarvis…",4000);composer.setMinLines(1);composer.setMaxLines(4);composer.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_FLAG_MULTI_LINE|InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);composer.setContentDescription("Mensaje para Jarvis");chatPage.addView(composer,new LinearLayout.LayoutParams(-1,-2));gap(chatPage,6);
        mic=button("Hablar",this::listen);mic.setContentDescription("Hablar con Jarvis");send=button("Enviar",()-> { if(busy)cancelRequest();else { String value=composer.getText().toString().trim();if(!value.isEmpty()) { composer.setText("");submit(value); } } });send.setTextColor(BG);send.setBackground(background(ACCENT,14));buttonRow(chatPage,mic,send);
        pages.addView(chatPage,new FrameLayout.LayoutParams(-1,-1));renderMessages();bottom();
    }
    private TextView bubble(String role,String value) {
        LinearLayout box=column();box.setPadding(dp(15),dp(12),dp(15),dp(13));box.setBackground(background(role.equals("user")?0xff1d3242:CARD,17));
        LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,-2);lp.setMargins(role.equals("user")?dp(28):0,0,role.equals("user")?0:dp(12),dp(12));chatMessages.addView(box,lp);
        TextView label=text(role.equals("user")?"TÚ":"JARVIS",10,role.equals("user")?MUTED:ACCENT);label.setTypeface(null,Typeface.BOLD);box.addView(label);gap(box,5);TextView body=text(value,16,TEXT);body.setTextIsSelectable(true);box.addView(body);return body;
    }
    private void renderMessages() {
        chatMessages.removeAllViews();
        if (messages.isEmpty()) {
            bubble("assistant", "Hola. Estoy aquí contigo. ¿Qué te gustaría lograr hoy?");
        }
        int first = Math.max(0, messages.size() - visibleHistory);
        for (ChatMessage message : messages.subList(first, messages.size())) {
            bubble(message.role, message.content);
        }
        updateHistoryButton();
    }

    private void clearConversation() {
        cancelRequest();
        messages.clear();
        liveReply = null;
        visibleHistory = HISTORY_PAGE_SIZE;
        store.saveAsync(messages);
        renderMessages();
        bottom();
    }

    private void showOlderMessages() {
        if (busy) return;
        int previousHeight = chatMessages.getHeight();
        int previousScroll = chatScroll.getScrollY();
        visibleHistory = Math.min(visibleHistory + HISTORY_PAGE_SIZE, ChatStore.MAX_MESSAGES);
        liveReply = null;
        renderMessages();
        afterChatLayout(() -> chatScroll.scrollTo(
            0, previousScroll + Math.max(0, chatMessages.getHeight() - previousHeight)
        ));
    }

    private void updateHistoryButton() {
        olderMessages.setVisibility(messages.size() > visibleHistory ? View.VISIBLE : View.GONE);
        olderMessages.setEnabled(!busy);
    }

    private void bottom() {
        if (scrollPending) return;
        scrollPending = true;
        afterChatLayout(() -> {
            scrollPending = false;
            chatScroll.scrollTo(0, chatMessages.getHeight());
        });
    }

    private void afterChatLayout(Runnable action) {
        chatScroll.getViewTreeObserver().addOnPreDrawListener(new ViewTreeObserver.OnPreDrawListener() {
            @Override public boolean onPreDraw() {
                chatScroll.getViewTreeObserver().removeOnPreDrawListener(this);
                action.run();
                return true;
            }
        });
    }

    private boolean nearBottom() {
        return chatMessages.getHeight() - chatScroll.getHeight() - chatScroll.getScrollY() <= dp(60);
    }

    private void appendBubble(String role, String text) {
        bubble(role, text);
        while (chatMessages.getChildCount() > visibleHistory) chatMessages.removeViewAt(0);
    }

    private void recordMessage(String role, String text) {
        messages.add(new ChatMessage(role, text));
        if (messages.size() > ChatStore.MAX_MESSAGES) messages.remove(0);
        store.saveAsync(messages);
        updateHistoryButton();
    }

    private void add(String role, String text) {
        recordMessage(role, text);
        appendBubble(role, text);
        bottom();
    }
    private void reply(String value) { add("assistant",value);setStatus("Aquí contigo · listo para ayudarte","idle");speak(value); }
    private void setStatus(String label,String state) { status.setText(label);orb.state(state);if(companionOrb!=null)companionOrb.state(state); }
    private void buildCompanion() {
        LinearLayout content=column();content.addView(heading("Aquí contigo",27));content.addView(text("Un poco de compañía. Un paso de progreso.",14,MUTED));gap(content,14);
        LinearLayout face=card(content,"Tu espacio de calma","Los colores indican si escucho, pienso o hablo.");companionOrb=new OrbView(this);face.addView(companionOrb,new LinearLayout.LayoutParams(-1,dp(155)));gap(content,14);
        LinearLayout focus=card(content,"Enfoque amable","Elige una sola cosa. Yo te aviso cuando toque descansar.");goalInput=input("¿Qué vas a hacer?",120);goalInput.setSingleLine(true);goalInput.setText(prefs.getString("focus_goal",""));focus.addView(goalInput);gap(focus,12);focusClock=heading("25:00",40);focusClock.setGravity(Gravity.CENTER);focus.addView(focusClock);focusLabel=text("Todo empieza con un bloque pequeño.",13,MUTED);focus.addView(focusLabel);
        buttonRow(focus,button("15 min",()->startFocus(15)),button("25 min",()->startFocus(25)),button("50 min",()->startFocus(50)));
        buttonRow(focus,button("Pausar / seguir",()-> { if(prefs.getLong("focus_end",0)>0)pauseFocus();else resumeFocus(); }),button("Terminar",()-> { stopFocus();reply("Bloque terminado. Quédate con el paso que sí diste; podemos empezar otro cuando quieras."); }));gap(content,14);
        LinearLayout camera=card(content,"Mirada local","La vista se queda en tu teléfono. La cámara se apaga al salir de esta pantalla o bloquear el celular.");cameraStatus=text("Cámara apagada",13,MUTED);camera.addView(cameraStatus);gap(camera,8);cameraBox=column();camera.addView(cameraBox);cameraButton=button("Encender cámara",()-> { if(preview==null)openCamera();else closeCamera(); });camera.addView(cameraButton);gap(content,14);
        LinearLayout support=card(content,"Si te cuesta empezar","Sin presión: reduce la tarea al primer movimiento.");support.addView(button("Necesito un empujón",()->reply(supportMessage())));gap(content,12);
        companionPage=column();companionPage.addView(scroll(content),new LinearLayout.LayoutParams(-1,-1));pages.addView(companionPage,new FrameLayout.LayoutParams(-1,-1));
    }
    private String supportMessage() { return switch(prefs.getString("style","Cercano")) { case "Directo" -> "Elige una tarea, quita una distracción y trabaja cinco minutos. Empieza por abrir lo que necesitas.";case "Suave" -> "No tienes que resolverlo todo ahora. Respira un momento y elige un paso tan pequeño que puedas hacerlo hoy.";default -> "Vamos juntos. ¿Y si solo hacemos los primeros cinco minutos? Abre lo que necesitas; el resto lo vemos después."; }; }
    private Spinner spinner(String[] values,String selected) { Spinner s=new Spinner(this);s.setPopupBackgroundDrawable(background(CARD,12));ArrayAdapter<String> a=new ArrayAdapter<>(this,android.R.layout.simple_spinner_item,values);a.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);s.setAdapter(a);s.setSelection(Math.max(0,Arrays.asList(values).indexOf(selected)));s.setMinimumHeight(dp(48));return s; }
    private void buildSettings() {
        LinearLayout content=column();content.addView(heading("Hazlo tuyo",27));content.addView(text("Jarvis Personal · Android · beta 0.1.1",13,MUTED));gap(content,16);
        LinearLayout brain=card(content,"Cerebro en Groq","El texto de la conversación se envía a Groq y necesita Internet. Las herramientas locales funcionan sin clave. La cámara no envía imágenes.");
        credentialStatus=text(vault.available()?"Clave cifrada guardada en este teléfono":"Añade tu clave personal para conversar",13,ACCENT);brain.addView(credentialStatus);gap(brain,10);
        keyInput=input("Pega tu clave de Groq",256);keyInput.setSingleLine(true);keyInput.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_PASSWORD);keyInput.setSaveEnabled(false);keyInput.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO_EXCLUDE_DESCENDANTS);keyInput.setOnFocusChangeListener((v,focus)-> { if(focus)getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);else getWindow().clearFlags(WindowManager.LayoutParams.FLAG_SECURE); });brain.addView(keyInput);
        brain.addView(button("Guardar clave",()-> { String key=keyInput.getText().toString().trim();if(!key.startsWith("gsk_")||key.length()<25) { credentialStatus.setText("Introduce una clave de Groq válida. No se ha cambiado la clave guardada.");return; }try { vault.save(key);keyInput.setText("");keyInput.clearFocus();credentialStatus.setText("Clave cifrada guardada. Ya puedes conversar.");setStatus("Cerebro configurado · envía un mensaje para comprobarlo","idle"); }catch(Exception e) { credentialStatus.setText("No pude guardar la clave de forma segura. Inténtalo de nuevo."); } }));
        gap(brain,8);brain.addView(text("Modelo",12,MUTED));modelChoice=spinner(new String[]{"Equilibrado · GPT OSS 120B","Rápido · GPT OSS 20B"},prefs.getString("model_label","Rápido · GPT OSS 20B"));brain.addView(modelChoice);
        brain.addView(text("Los límites dependen de tu cuenta. Esta beta no incluye una suscripción ni una clave compartida.",12,MUTED));gap(content,14);
        LinearLayout personal=card(content,"Tu forma de conversar","");nameInput=input("¿Cómo te llamas?",80);nameInput.setSingleLine(true);nameInput.setText(prefs.getString("name",""));personal.addView(nameInput);gap(personal,8);styleChoice=spinner(new String[]{"Cercano","Suave","Directo"},prefs.getString("style","Cercano"));personal.addView(styleChoice);
        readSwitch=new Switch(this);readSwitch.setText("Leer respuestas en voz alta");readSwitch.setTextColor(TEXT);readSwitch.setChecked(prefs.getBoolean("read",true));readSwitch.setMinHeight(dp(48));personal.addView(readSwitch);personal.addView(button("Probar voz española",()->speak("Hola. Soy Jarvis. Estoy aquí para acompañarte, paso a paso.",true)));
        personal.addView(text("Hablar usa el reconocimiento de Android. Intento usar el servicio local si está disponible; según el teléfono, su servicio puede enviar audio a su proveedor. No escucho en segundo plano.",12,MUTED));gap(content,14);
        LinearLayout memory=card(content,"Lo que quieres recordar","Estas notas permanecen en este teléfono. Puedes decidir si compartirlas al conversar.");notesInput=input("Tus objetivos, preferencias o notas…",2000);notesInput.setText(prefs.getString("notes",""));notesInput.setMinLines(3);notesInput.setGravity(Gravity.TOP);memory.addView(notesInput);shareNotes=new Switch(this);shareNotes.setText("Compartir estas notas con Groq");shareNotes.setTextColor(TEXT);shareNotes.setChecked(prefs.getBoolean("share_notes",false));shareNotes.setMinHeight(dp(48));memory.addView(shareNotes);gap(content,12);
        Button save=button("Guardar preferencias",this::saveSettings);save.setTextColor(BG);save.setBackground(background(ACCENT,14));content.addView(save);gap(content,14);
        LinearLayout limits=card(content,"Una beta para empezar","En esta versión no se controlan otras apps ni Windows. El enfoque usa un temporizador; no detecta si abriste redes sociales. La cámara muestra presencia solo si el teléfono lo admite.");limits.addView(text("Los avisos de descanso pueden retrasarse si Android restringe la batería. Si reinicias el celular, abre Jarvis para recuperar tu sesión.",12,MUTED));limits.addView(button("Quitar clave de este teléfono",()->new AlertDialog.Builder(this).setTitle("¿Quitar la clave?").setMessage("Podrás seguir usando las funciones locales.").setNegativeButton("Conservar",null).setPositiveButton("Quitar",(d,w)-> { cancelRequest();try { vault.save("");credentialStatus.setText("Clave eliminada de este teléfono"); }catch(Exception e){credentialStatus.setText("No se pudo quitar la clave.");} }).show()));gap(content,16);
        settingsPage=column();settingsPage.addView(scroll(content),new LinearLayout.LayoutParams(-1,-1));pages.addView(settingsPage,new FrameLayout.LayoutParams(-1,-1));
    }
    private void saveSettings() { prefs.edit().putString("name",nameInput.getText().toString().trim()).putString("style",styleChoice.getSelectedItem().toString()).putString("model_label",modelChoice.getSelectedItem().toString()).putString("notes",notesInput.getText().toString()).putBoolean("share_notes",shareNotes.isChecked()).putBoolean("read",readSwitch.isChecked()).apply();Toast.makeText(this,"Preferencias guardadas",Toast.LENGTH_SHORT).show(); }
    private void showTab(int tab) {
        if (tab != 1) closeCamera();
        if (tab == 2 && settingsPage == null) buildSettings();
        selectedTab = tab;
        chatPage.setVisibility(tab == 0 ? View.VISIBLE : View.GONE);
        companionPage.setVisibility(tab == 1 ? View.VISIBLE : View.GONE);
        if (settingsPage != null) settingsPage.setVisibility(tab == 2 ? View.VISIBLE : View.GONE);
        if (tab != 2 && keyInput != null) {
            keyInput.clearFocus();
            getWindow().clearFlags(WindowManager.LayoutParams.FLAG_SECURE);
        }
        getSystemService(InputMethodManager.class).hideSoftInputFromWindow(root.getWindowToken(), 0);
        updateFocus();
    }

    private void submit(String text) {
        if(busy) { Toast.makeText(this,"Detén la respuesta actual para enviar otra.",Toast.LENGTH_SHORT).show();return; }
        if (liveReply != null) {
            chatMessages.removeView((View) liveReply.getParent());
            liveReply = null;
        }
        stopListening();if(tts!=null)tts.stop();showTab(0);add("user",text);LocalCommands.Command command=LocalCommands.parse(text);
        try {
            switch(command.kind()) {
                case "help" -> reply("Podemos conversar, practicar, programar o planear tu día. También puedes decir: «inicia enfoque de 25 minutos», «calcula 137 por 29», «recuerda que quiero estudiar», «enciende la cámara», «enciende la linterna» o «cambia el holograma a violeta». Las acciones locales no gastan cuota de Groq.");
                case "calculate" -> { double n=Calculator.evaluate(command.value());reply("El resultado es "+(n==(long)n?Long.toString((long)n):Double.toString(n))+"."); }
                case "time" -> reply("Son las "+DateFormat.getTimeInstance(DateFormat.SHORT,new Locale("es","PE")).format(new Date())+".");
                case "battery" -> { BatteryManager b=getSystemService(BatteryManager.class);reply("La batería está al "+b.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)+" por ciento."); }
                case "color" -> { prefs.edit().putString("color",command.value()).apply();applyColor(command.value());reply("Listo. Tu holograma ahora es "+command.value()+". Cambiaré de color al escuchar, pensar y hablar."); }
                case "remember" -> { String old=prefs.getString("notes","");String note=command.value();if(old.length()+note.length()>1950)reply("Tus notas están llenas. Puedes editarlas en Ajustes para hacer espacio.");else { String value=old+(old.isEmpty()?"":"\n")+note;prefs.edit().putString("notes",value).apply();if(notesInput!=null)notesInput.setText(value);reply("Lo guardé en tus notas de este teléfono."); } }
                case "notes" -> { String notes=prefs.getString("notes","");reply(notes.isEmpty()?"Aún no tengo notas. Di «recuerda que…» para guardar una.":"Tus notas:\n"+notes); }
                case "camera" -> { if(command.value().equals("on")) { showTab(1);openCamera(); }else { closeCamera();reply("La cámara está apagada."); } }
                case "torch" -> torch(command.value().equals("on"));
                case "focus" -> { switch(command.value()) { case "pause"->pauseFocus();case "resume"->resumeFocus();case "stop"->{stopFocus();reply("Enfoque terminado. Podemos empezar otro bloque cuando estés listo.");}default->startFocus(Integer.parseInt(command.value())); } }
                default -> ask();
            }
        } catch(IllegalArgumentException e) { reply(e.getMessage()==null?"Revisa esa petición.":e.getMessage()); }
    }
    private void ask() {
        if(!vault.available()) { reply("Para conversar necesito tu clave de Groq. Guárdala en Ajustes. Mientras tanto puedo ayudarte con enfoque, notas, cálculos y herramientas locales.");return; }
        busy=true;send.setText("Detener");mic.setEnabled(false);setStatus("Pensando contigo…","thinking");
        updateHistoryButton();
        liveReply=bubble("assistant","…");bottom();
        int id=++requestId;GroqClient requestClient=new GroqClient();client=requestClient;List<ChatMessage> snapshot=new ArrayList<>(messages);String model=prefs.getString("model_label","Rápido · GPT OSS 20B").startsWith("Rápido")?"openai/gpt-oss-20b":"openai/gpt-oss-120b";
        String system=ConversationPolicy.system(prefs.getString("name",""),prefs.getString("style","Cercano"),prefs.getBoolean("share_notes",false)?prefs.getString("notes",""):"");
        network.execute(()-> {
            String key;
            try { key=vault.load(); }catch(Exception e) { handler.post(()->requestError(id,"No pude abrir la clave cifrada. Vuelve a guardarla en Ajustes."));return; }
            requestClient.ask(key,model,snapshot,system,new GroqClient.Listener() {
                @Override public void partial(String value) {
                    handler.post(() -> {
                        if (id != requestId || destroyed) return;
                        boolean follow = nearBottom();
                        liveReply.setText(value);
                        if (follow) bottom();
                    });
                }
                @Override public void complete(String value) {
                    handler.post(() -> {
                        if (id != requestId || destroyed) return;
                        boolean follow = nearBottom();
                        liveReply.setText(value);
                        recordMessage("assistant", value);
                        liveReply = null;
                        finishRequest();
                        if (follow) bottom();
                        setStatus("Aquí contigo · listo para ayudarte", "idle");
                        speak(value);
                    });
                }
                @Override public void error(String value) { handler.post(()->requestError(id,value)); }
            });
        });
    }
    private void requestError(int id,String value) { if(id!=requestId||destroyed)return;liveReply.setText(value);finishRequest();setStatus("Necesita atención · puedes seguir usando herramientas locales","error"); }
    private void finishRequest() {
        busy = false;
        send.setText("Enviar");
        mic.setEnabled(true);
        if (liveReply == null) {
            while (chatMessages.getChildCount() > visibleHistory) chatMessages.removeViewAt(0);
        }
        updateHistoryButton();
        scheduleFocusUpdate();
    }
    private void cancelRequest() { ++requestId;client.cancel();if(busy&&liveReply!=null)liveReply.setText("Respuesta detenida. Puedes enviar otra petición.");finishRequest();if(tts!=null)tts.stop();setStatus("En pausa · aquí cuando quieras","idle"); }

    private void initVoice() {
        tts=new TextToSpeech(this,result-> { if(destroyed)return;voiceReady=result==TextToSpeech.SUCCESS;if(voiceReady) { int lang=tts.setLanguage(new Locale("es","PE"));if(lang<0)lang=tts.setLanguage(new Locale("es"));voiceReady=lang>=0;tts.setSpeechRate(1.02f);tts.setAudioAttributes(new android.media.AudioAttributes.Builder().setUsage(android.media.AudioAttributes.USAGE_ASSISTANT).setContentType(android.media.AudioAttributes.CONTENT_TYPE_SPEECH).build()); } });
        tts.setOnUtteranceProgressListener(new UtteranceProgressListener() {
            @Override public void onStart(String id) { handler.post(()-> { if(id.equals(utterance)&&!destroyed&&!busy)setStatus("Hablando contigo…","speaking"); }); }
            @Override public void onDone(String id) { handler.post(()-> { if(id.equals(utterance)&&!destroyed&&!busy)setStatus("Aquí contigo · listo para ayudarte","idle"); }); }
            @Override public void onError(String id) { handler.post(()-> { if(!destroyed)setStatus("No se pudo reproducir la voz. Revisa las voces españolas del teléfono.","error"); }); }
        });
    }
    private void speak(String value) { speak(value,false); }
    private void speak(String value,boolean force) {
        if(!resumed || (!force&&!prefs.getBoolean("read",true)))return;
        if(!voiceReady) { if(force)Toast.makeText(this,"La voz española no está disponible todavía. Revisa el motor de voz del teléfono.",Toast.LENGTH_LONG).show();return; }
        String spoken=value.replaceAll("(?s)```.*?```","El código está en la conversación.").replaceAll("https?://\\S+","").replaceAll("[*#`_]","");
        if(spoken.length()>650)spoken=spoken.substring(0,650)+". El resto está en la conversación.";
        utterance=UUID.randomUUID().toString();tts.speak(spoken,TextToSpeech.QUEUE_FLUSH,null,utterance);
    }
    private void listen() {
        if(listening) { stopListening();return; }if(busy)return;
        if(checkSelfPermission(Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED) { requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO},10);return; }
        if(!SpeechRecognizer.isRecognitionAvailable(this)) { reply("Este teléfono no tiene un servicio de reconocimiento de voz disponible. Puedes escribirme o habilitar uno desde los ajustes de Android.");return; }
        if(tts!=null)tts.stop();if(recognizer!=null)recognizer.destroy();
        recognizer=SpeechRecognizer.isOnDeviceRecognitionAvailable(this)?SpeechRecognizer.createOnDeviceSpeechRecognizer(this):SpeechRecognizer.createSpeechRecognizer(this);
        recognizer.setRecognitionListener(new RecognitionListener() {
            @Override public void onReadyForSpeech(Bundle b){setStatus("Te escucho…","listening");}
            @Override public void onBeginningOfSpeech(){}
            @Override public void onRmsChanged(float rms){}
            @Override public void onBufferReceived(byte[] bytes){}
            @Override public void onEndOfSpeech(){setStatus("Entendiendo tu voz…","thinking");}
            @Override public void onError(int error){listening=false;mic.setText("Hablar");if(!resumed)return;setStatus(error==SpeechRecognizer.ERROR_NO_MATCH||error==SpeechRecognizer.ERROR_SPEECH_TIMEOUT?"No alcancé a oírte. Pulsa Hablar para intentar otra vez.":"La voz no está disponible ahora. Puedes escribirme.","idle");}
            @Override public void onResults(Bundle b){listening=false;mic.setText("Hablar");if(!resumed)return;ArrayList<String> values=b.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);if(values!=null&&!values.isEmpty())submit(values.get(0));else setStatus("No alcancé a oírte","idle");}
            @Override public void onPartialResults(Bundle b){}
            @Override public void onEvent(int e,Bundle b){}
        });
        Intent intent=new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,RecognizerIntent.LANGUAGE_MODEL_FREE_FORM).putExtra(RecognizerIntent.EXTRA_LANGUAGE,"es-PE").putExtra(RecognizerIntent.EXTRA_MAX_RESULTS,1).putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE,true);
        try { listening=true;mic.setText("Parar voz");setStatus("Preparando la escucha…","listening");recognizer.startListening(intent); }
        catch(Exception e) { listening=false;mic.setText("Hablar");setStatus("No pude iniciar el micrófono. Puedes escribirme.","error"); }
    }
    private void stopListening() { listening=false;if(mic!=null)mic.setText("Hablar");if(recognizer!=null)recognizer.cancel(); }

    private void startFocus(int minutes) {
        if(minutes<1||minutes>120)throw new IllegalArgumentException("Elige entre 1 y 120 minutos.");
        long end=System.currentTimeMillis()+minutes*60000L;
        prefs.edit().putLong("focus_end",end).putLong("focus_paused",0).putLong("focus_completed",0).putString("focus_goal",goalInput.getText().toString().trim()).apply();FocusReceiver.schedule(this,end);updateFocus();
        reply("Vamos con "+minutes+" minutos. Quédate con una sola tarea; no hace falta hacerlo perfecto. Te avisaré cuando toque descansar.");
        if(checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED)requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},12);
    }
    private void pauseFocus() { long end=prefs.getLong("focus_end",0);if(end<=System.currentTimeMillis()){reply("No hay un bloque activo para pausar.");return;}prefs.edit().putLong("focus_paused",end-System.currentTimeMillis()).putLong("focus_end",0).apply();FocusReceiver.cancel(this);updateFocus();reply("Pausado. Respira; seguimos cuando estés listo."); }
    private void resumeFocus() { long left=prefs.getLong("focus_paused",0);if(left<=0){reply("Empieza un bloque de 15, 25 o 50 minutos en Compañero.");return;}long end=System.currentTimeMillis()+left;prefs.edit().putLong("focus_end",end).putLong("focus_paused",0).apply();FocusReceiver.schedule(this,end);updateFocus();reply("Seguimos. Solo el siguiente paso."); }
    private void stopFocus() { FocusReceiver.cancel(this);prefs.edit().putLong("focus_end",0).putLong("focus_paused",0).putLong("focus_completed",0).apply();updateFocus(); }
    private void updateFocus() {
        long end=prefs.getLong("focus_end",0),paused=prefs.getLong("focus_paused",0),now=System.currentTimeMillis();
        if(end>0 && end<=now) { FocusReceiver.cancel(this);prefs.edit().putLong("focus_end",0).putLong("focus_completed",now).apply();end=0; }
        long left=end>0?Math.max(0,end-now):paused;
        if (selectedTab == 1) {
            focusClock.setText(left>0?String.format(Locale.ROOT,"%02d:%02d",(left+999)/60000,((left+999)/1000)%60):"25:00");
            String goal = prefs.getString("focus_goal", "");
            String label = "Elige un bloque para comenzar.";
            if (end > 0) label = "En marcha · " + (goal.isEmpty() ? "una cosa a la vez" : goal);
            else if (paused > 0) label = "En pausa · continúa cuando quieras";
            if (!label.contentEquals(focusLabel.getText())) focusLabel.setText(label);
        }
        long completed=prefs.getLong("focus_completed",0);
        if(completed>0 && !busy) { prefs.edit().putLong("focus_completed",0).apply();reply("Lo hiciste. Tu bloque terminó. Descansa cinco minutos: estira el cuerpo y toma un poco de agua."); }
        scheduleFocusUpdate();
    }

    private void scheduleFocusUpdate() {
        handler.removeCallbacks(ticker);
        if (!resumed) return;
        long end = prefs.getLong("focus_end", 0);
        if (end > 0) {
            long remaining = Math.max(1, end - System.currentTimeMillis());
            handler.postDelayed(ticker, selectedTab == 1 ? Math.min(1000, remaining) : remaining);
        } else if (!busy && prefs.getLong("focus_completed", 0) > 0) {
            handler.postDelayed(ticker, 1000);
        }
    }

    private void restoreFocus() {
        updateFocus();
        long end = prefs.getLong("focus_end", 0);
        if (end > System.currentTimeMillis()) FocusReceiver.schedule(this, end);
    }
    private void openCamera() {
        if(checkSelfPermission(Manifest.permission.CAMERA)!=PackageManager.PERMISSION_GRANTED) { requestPermissions(new String[]{Manifest.permission.CAMERA},11);return; }
        if(preview!=null)return;showTab(1);cameraStatus.setText("Abriendo la cámara frontal…");cameraButton.setText("Apagar cámara");
        preview=new CameraPreview(this,value->runOnUiThread(()->cameraStatus.setText(value)));cameraBox.addView(preview,new LinearLayout.LayoutParams(-1,dp(200)));setStatus("Usando la cámara local","tool");
    }
    private void closeCamera() { boolean wasOpen=preview!=null;if(preview!=null) { preview.close();cameraBox.removeAllViews();preview=null; }if(cameraStatus!=null)cameraStatus.setText("Cámara apagada");if(cameraButton!=null)cameraButton.setText("Encender cámara");if(wasOpen&&!busy&&!listening)setStatus("Aquí contigo · listo para ayudarte","idle"); }
    private void torch(boolean on) {
        if(checkSelfPermission(Manifest.permission.CAMERA)!=PackageManager.PERMISSION_GRANTED) { reply("Para usar la linterna, habilita la cámara al abrirla en Compañero y luego repite la orden.");return; }
        closeCamera();CameraManager manager=getSystemService(CameraManager.class);
        try { if(torchId==null)for(String id:manager.getCameraIdList()){var c=manager.getCameraCharacteristics(id);if(Boolean.TRUE.equals(c.get(CameraCharacteristics.FLASH_INFO_AVAILABLE))){torchId=id;break;}}if(torchId==null){reply("Este dispositivo no tiene linterna disponible.");return;}manager.setTorchMode(torchId,on);reply(on?"Linterna encendida.":"Linterna apagada."); }
        catch(Exception e){reply("No pude cambiar la linterna. Otra app podría estar usando la cámara.");}
    }
    private void applyColor(String color) { int value=switch(color){case "verde"->0xff50e49f;case "violeta"->0xffa68bfa;case "rojo"->0xfffb7185;case "dorado"->0xffffc568;case "rosa"->0xfff09edb;default->ACCENT;};orb.color(value);companionOrb.color(value); }
    @Override public void onRequestPermissionsResult(int request,String[] permissions,int[] results) { super.onRequestPermissionsResult(request,permissions,results);boolean granted=results.length>0&&results[0]==PackageManager.PERMISSION_GRANTED;if(request==10){if(granted)listen();else setStatus("Micrófono sin permiso · puedes escribirme","idle");}if(request==11){if(granted&&selectedTab==1)openCamera();else cameraStatus.setText("Cámara sin permiso. Puedes habilitarlo desde los ajustes de Android.");}if(request==12&&!granted)Toast.makeText(this,"El temporizador funciona; los avisos fuera de la app necesitan notificaciones.",Toast.LENGTH_LONG).show(); }
    @Override protected void onResume() { super.onResume();resumed=true;if(root!=null)restoreFocus(); }
    @Override protected void onPause() { resumed=false;handler.removeCallbacks(ticker);stopListening();closeCamera();if(tts!=null)tts.stop();if(!busy&&root!=null)setStatus("Aquí cuando vuelvas","idle");super.onPause(); }
    @Override protected void onDestroy() { destroyed=true;client.cancel();network.shutdownNow();handler.removeCallbacksAndMessages(null);if(recognizer!=null)recognizer.destroy();if(tts!=null)tts.shutdown();if(torchId!=null)try{getSystemService(CameraManager.class).setTorchMode(torchId,false);}catch(Exception ignored){}super.onDestroy(); }
}
