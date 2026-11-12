package io.jarvispersonal.mobile;

import android.app.*;
import android.content.*;

public final class FocusReceiver extends BroadcastReceiver {
    public static final String CHANNEL="jarvis_focus";
    public static void channel(Context c) {
        c.getSystemService(NotificationManager.class).createNotificationChannel(
            new NotificationChannel(CHANNEL,"Sesiones de enfoque",NotificationManager.IMPORTANCE_DEFAULT));
    }
    public static void schedule(Context c,long end) {
        Intent intent=new Intent(c,FocusReceiver.class).putExtra("end",end);
        PendingIntent pending=PendingIntent.getBroadcast(c,1,intent,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
        c.getSystemService(AlarmManager.class).setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP,end,pending);
    }
    public static void cancel(Context c) {
        PendingIntent pending=PendingIntent.getBroadcast(c,1,new Intent(c,FocusReceiver.class),PendingIntent.FLAG_NO_CREATE|PendingIntent.FLAG_IMMUTABLE);
        if(pending!=null) { c.getSystemService(AlarmManager.class).cancel(pending);pending.cancel(); }
    }
    @Override public void onReceive(Context c,Intent intent) {
        var p=c.getSharedPreferences("settings",Context.MODE_PRIVATE);
        long end=p.getLong("focus_end",0);
        if(end==0 || end!=intent.getLongExtra("end",-1) || System.currentTimeMillis()<end)return;
        p.edit().putLong("focus_end",0).putLong("focus_completed",System.currentTimeMillis()).apply();
        channel(c);
        if(c.checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS)!=android.content.pm.PackageManager.PERMISSION_GRANTED)return;
        PendingIntent open=PendingIntent.getActivity(c,0,new Intent(c,MainActivity.class),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
        Notification notification=new Notification.Builder(c,CHANNEL).setSmallIcon(R.drawable.ic_jarvis)
            .setContentTitle("Lo hiciste. Es momento de descansar.")
            .setContentText("Tu bloque de enfoque terminó. Regálate una pausa y vuelve cuando estés listo.")
            .setContentIntent(open).setAutoCancel(true).build();
        c.getSystemService(NotificationManager.class).notify(1,notification);
    }
}
