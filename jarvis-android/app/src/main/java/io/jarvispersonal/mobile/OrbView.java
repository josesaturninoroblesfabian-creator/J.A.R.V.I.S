package io.jarvispersonal.mobile;

import android.content.Context;
import android.graphics.*;
import android.view.View;

/** Native canvas, capped at 12 fps only while active; no GPU model or video loop. */
public final class OrbView extends View {
    private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
    private String state="idle";
    private int idleColor=Color.rgb(94,225,242);
    private Shader glow;
    public OrbView(Context c) { super(c);setContentDescription("Rostro de Jarvis. En espera."); }
    public void color(int color) { idleColor=color;updateGlow();invalidate(); }
    public void state(String value) {
        if (state.equals(value)) return;
        state = value;
        setContentDescription("Rostro de Jarvis. " + value);
        updateGlow();
        invalidate();
    }
    private void updateGlow() { if(getWidth()>0&&getHeight()>0) { int c=color();glow=new RadialGradient(getWidth()/2f,getHeight()/2f,Math.min(getWidth(),getHeight())*.43f+10,new int[]{Color.argb(35,Color.red(c),Color.green(c),Color.blue(c)),Color.TRANSPARENT},null,Shader.TileMode.CLAMP); } }
    @Override protected void onSizeChanged(int w,int h,int oldw,int oldh) { super.onSizeChanged(w,h,oldw,oldh);updateGlow(); }
    private int color() { return switch(state) {
        case "listening" -> Color.rgb(80,228,159); case "thinking" -> Color.rgb(166,139,250);
        case "speaking" -> Color.rgb(255,197,104);case "tool" -> Color.rgb(78,158,255);
        case "error" -> Color.rgb(251,113,133);default -> idleColor; }; }
    @Override protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);float w=getWidth(),h=getHeight(),r=Math.min(w,h)*.43f,cx=w/2,cy=h/2;
        int color=color();long time=android.os.SystemClock.uptimeMillis();
        boolean animating = state.equals("listening") || state.equals("thinking") || state.equals("speaking");
        float pulse = animating ? (float)Math.sin(time / 350.0) * 3 : 0;
        paint.setStyle(Paint.Style.FILL);paint.setShader(glow);
        canvas.drawCircle(cx,cy,r+10,paint);paint.setShader(null);
        paint.setColor(Color.rgb(18,31,49));canvas.drawCircle(cx,cy,r-8,paint);
        paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(2);paint.setColor(color);canvas.drawCircle(cx,cy,r+pulse,paint);
        paint.setColor(Color.argb(60,Color.red(color),Color.green(color),Color.blue(color)));paint.setStrokeWidth(1);canvas.drawCircle(cx,cy,r-5,paint);
        paint.setColor(color);paint.setStrokeCap(Paint.Cap.ROUND);paint.setStrokeWidth(r*.12f);
        float eyeY=cy-r*.12f;canvas.drawLine(cx-r*.42f,eyeY,cx-r*.25f,eyeY,paint);canvas.drawLine(cx+r*.25f,eyeY,cx+r*.42f,eyeY,paint);
        paint.setStrokeWidth(3);canvas.drawArc(cx-r*.24f,cy+r*.15f,cx+r*.24f,cy+r*.4f,5,170,false,paint);
        if (animating && isShown() && getWindowVisibility() == VISIBLE) postInvalidateDelayed(83);
    }
}
