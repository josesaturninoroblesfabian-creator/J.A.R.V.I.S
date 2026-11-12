package io.jarvispersonal.mobile;

import android.content.Context;
import android.hardware.Camera;
import android.view.SurfaceHolder;
import android.view.SurfaceView;
import java.util.List;

/** Explicit, local-only front camera preview. No frames are saved or sent to an API. */
@SuppressWarnings("deprecation")
public final class CameraPreview extends SurfaceView implements SurfaceHolder.Callback {
    public interface Status { void changed(String text); }
    private Camera camera;
    private final Status status;
    private boolean stopped;
    private String lastStatus="";
    private void emit(String value) { if(!value.equals(lastStatus)) { lastStatus=value;status.changed(value); } }
    public CameraPreview(Context context,Status status) { super(context);this.status=status;getHolder().addCallback(this);setContentDescription("Vista local de la cámara frontal"); }
    @Override public void surfaceCreated(SurfaceHolder holder) {
        if(stopped)return;
        try {
            int id=-1;Camera.CameraInfo info=new Camera.CameraInfo();
            for(int i=0;i<Camera.getNumberOfCameras();i++) { Camera.getCameraInfo(i,info);if(info.facing==Camera.CameraInfo.CAMERA_FACING_FRONT) { id=i;break; } }
            if(id<0) { emit("Este dispositivo no tiene cámara frontal disponible.");return; }
            Camera.getCameraInfo(id,info);camera=Camera.open(id);
            Camera.Parameters params=camera.getParameters();List<Camera.Size> sizes=params.getSupportedPreviewSizes();
            Camera.Size selected=null;
            for(Camera.Size s:sizes)if(s.width<=640 && (selected==null||s.width>selected.width))selected=s;
            if(selected==null)selected=sizes.get(sizes.size()-1);
            params.setPreviewSize(selected.width,selected.height);camera.setParameters(params);
            int rotation=((android.app.Activity)getContext()).getWindowManager().getDefaultDisplay().getRotation()*90;
            camera.setDisplayOrientation((360-(info.orientation+rotation)%360)%360);
            camera.setPreviewDisplay(holder);camera.startPreview();
            emit("Cámara encendida · vista local");
            if(params.getMaxNumDetectedFaces()>0) {
                try {
                    camera.setFaceDetectionListener((faces,c)->emit(faces.length>0?"Estoy aquí contigo · presencia detectada localmente":"Cámara encendida · buscando presencia"));
                    camera.startFaceDetection();
                } catch(RuntimeException unsupported) { emit("Cámara encendida · detección de presencia no disponible."); }
            } else emit("Cámara encendida · vista local. Este teléfono no ofrece detección de presencia.");
        } catch(Exception e) { close();emit("No pude abrir la cámara. Comprueba el permiso o cierra otra app que la esté usando."); }
    }
    public void close() { stopped=true;Camera c=camera;camera=null;if(c!=null) { try { c.setFaceDetectionListener(null);c.stopPreview(); } catch(Exception ignored) {} c.release(); } }
    @Override public void surfaceDestroyed(SurfaceHolder holder) { close(); }
    @Override public void surfaceChanged(SurfaceHolder holder,int format,int width,int height) {}
}
